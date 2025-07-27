from tools import store_long_term_memory
import json, datetime
import networkx as nx
from langchain.chat_models import init_chat_model
from qdrant_client import QdrantClient
from schema import reasoning_output,shorttermemory,graphsummary
from qdrant_client.http import models as qdrant_models
from typing import List, Tuple
from pymongo import MongoClient
from langchain.schema import Document
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Qdrant

"""
Not related to venture bot, but a possible recommendation
"""



class GraphMemory:
    def __init__(self):
        self.graph_store = []
        self.llm = init_chat_model("gpt-4o-2024-08-06", temperature = 0.0, model_provider = "openai",api_key = api_key)
        self.qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)


    def store_graph(self, graph:nx.DiGraph, metadata:dict):
        graph_json = ReasoningGraph.seralize_graph(graph)
        
        if metadata is None:
            metadata = {}
        metadata['timestamp'] = str(datetime.datetime.now())
        metadata['type'] = "reasoning_graph"

        store_long_term_memory(graph_json,metadata["timestamp"])

   
    def manage_graph_memory(self, collection_name):
        qdrant_client = QdrantClient(url =qdrant_url, api_key = qdrant_api_key)

        search_filter = qdrant_models.Filter(
            must = [
                qdrant_models.FieldCondition(
                    keys = "type",
                    match = qdrant_models.MatchValue(value = "reasoning_graph")

                )
            ]

        )
        points = qdrant_client.scroll(
            collection_name = collection_name,
            filter = search_filter,
            limit = 100
        )[0]

        if len(points) > 5:
            points_sorted = sorted(points, key = lambda p: p.payload.get("timestamp"))
            oldest = points_sorted[0]
            graph_json = oldest.payload.get("input_text")

            summary = self.memory_summarizer(graph = graph_json)

            qdrant_client.delete(
                collection_name = collection_name,
                points_selector = qdrant_models.PointIdsList(points= [oldest.id])
            )
            store_long_term_memory(summary, str(datetime.datetime.now()))
    
    def store_long_term_memory(self,summary):
        client = MongoClient("mongodb://127.0.0.1:27017/")
        db = client.Memory
        collection = db.LongTermMemory

        learning = {
            "title":  summary['Title'],
            "Lesson": summary['Lesson']
        }
        insert_result = collection.insert_one(learning)
        if (insert_result):
            return True
        return False

    
    def memory_summarizer(self,graph):
        prompt = """
        <role>
        You are an AI Summarizer Assistant who is responsible for summarizing the graph and provide a lesson for a respective agent
        </role>
        <context>
        You are a part of AI Eval system for an AI Reservoir Engineer who should summarize the bad reasoning the agent has done in the past.
        You provide context to the agent, so next time it does not make a mistake.
        </context>

        <Graph>
        {graph}
        </Graph>
        """
        llm = init_chat_model("gpt-4o-2024-08-06", temperature = 0.0, model_provider = "openai",api_key = api_key)
        llm = llm.with_structured_output(shorttermemory)
        system_prompt = prompt.format(
            reasoning = graph
        )
        result = llm.invoke([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': "SUmmarize the bad reasoning"}
        ])
        return result
    
    def short_term_memory(self,graph_json):
        doc = Document(page_content = graph_json, metadata = metadata)

        embeddings = OpenAIEmbeddings(api_key = api_key)

        vectorstore = Qdrant.from_documents(
            [doc],
            embeddings,
            collection_name = "Short term Memory",
            url = qdrant_url,
            api_key = qdrant_api_key
        )
        if (vectorstore):
            return True
        return False
    
    def extract_data(self):
        collection_name = "Short term Memory"
        self.qdrant_client.create_payload_index(
            collection_name=collection_name,
            field_name="type",
            field_schema="keyword"
        )
        scroll_result = self.qdrant_client.scroll(
            collection_name=collection_name,
            with_payload=True,
            limit=100
        )
        points = scroll_result[0]
        extracted_graphs = []
        for point in points:
            payload = point.payload
            if "metadata" in payload:
                meta = payload.get("metadata")
                if meta.get('type') == 'reasoning_graph':
                    graph_json = payload.get("page_content")
                    try:
                        graph_data = json.loads(graph_json)
                        extracted_graphs.append(graph_data)
                    except Exception as e:
                        print("Error parsing graph JSON:", e)
        return extracted_graphs
        




class ReasoningGraph:
    def __init__(self, api_key=api_key, model_name="gpt-4o-2024-08-06", temperature=0.0, model_provider="openai"):
        self.llm = init_chat_model(model_name, temperature=temperature, model_provider=model_provider, api_key=api_key)
        self.qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    def initialize_graph(self,reasoning):
        prompt = """
        <role>
        You are an AI Graph Asistant who is responsible for creating the nodes and  edges for them
        </role>

        <context>
        You are part of a broader AI Eval System who is responsible for analyzing the reasoning process and creating nodes and edges for the 
        research process.
        Your job is to think critically, connect nodes together based on critical thinking.
        </context>

        <Example>
        This is an example to give an idea, do not take this as the input

        Input :
        1. Analyze OPEC+ supply cuts.
        2. Analyze inventory levels.
        3. Infer supply constraints from steps 1 and 2.
        4. Analyze macroeconomic indicators.
        5. Conclude bullish outlook based on steps 3 and 4.

        Output:
        [(1, 3),
        (2, 3),
        (3, 5),
        (4, 5)]
        
        </Example>
        <Output Structure>
        Provide a detail output step by step
        </Output Structure>

        <Reasoning>
        {reasoning}
        </Reasoning>
        """
        llm = init_chat_model("gpt-4o-2024-08-06", temperature = 0.0, model_provider = "openai",api_key = api_key)
        llm = llm.with_structured_output(reasoning_output)
        system_prompt = prompt.format(
            reasoning = reasoning
        )
        result = llm.invoke([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': "Analyze the data"}
        ])
        
        G = nx.DiGraph()
        
        #Add Nodes
        i = 0
        for text in result.Nodes:
            i+= 1
            G.add_node(i,text = text)
        
        for from_id,to_id in result.Edges:
            G.add_edge(from_id,to_id)
        
        return G

    def build_graph(self,nodes_list:List[Tuple[int, str]], edges_list : List[Tuple[int,int]]):
        G = nx.DiGraph()
        for step_id, text in nodes_list:
            G.add_node(step_id, text = text)
        for from_id, to_id in edges_list:
            G.add_edge(from_id, to_id)
        
        return G
    
    def seralize_graph(self,G: nx.DiGraph):
        data = {
            "nodes": [(n, G.nodes[n]['text']) for n in G.nodes()],
            "edges": list(G.edges())
        }
        return json.dumps(data)
    
    def deserialize_graph(self,json_str):
        data = json.loads(json_str)
        print("This is the data",data)
        G = nx.DiGraph()
        for key, values in data.items():
            if key == "nodes":
                for idx,value in values:
                    G.add_node(idx, text = value)
        for key, values in data.items():
            if values == "edges":
                for idx,value in values:
                    G.add_node(idx, text = value)
        return G    

    def compare_graphs(self, G1):
        compare = 0
        content = {}
        graphmemory = GraphMemory()
        for data in graphmemory.extract_data():
            output_ = json.dumps(data, indent=4)
            print("This is the output",output_)
            G2 = self.deserialize_graph(output_)
            print("G2 graph",G2)
            if (nx.graph_edit_distance(G1,G2) > compare):

                compare = nx.graph_edit_distance(G1,G2)
                content = data
        
        final_output = {}
        final_output['score'] = compare
        final_output['content'] = content

        lesson = self.lesson_agent(G1,G2,final_output['score'])
        return lesson
    def lesson_agent(self,G1, G2, score):
        prompt = """
        <role>
        You are an AI Lesson Agent who is responsible for looking at the data you get from 2 graphs and provide improvemnts to graph-1
        </role>

        <context>
        You are a part of a reasoning graph for an AI Reservoir Engineer. You will be give 2 graphs, Graph-1 and Graph-2.
        Graph-1 is in a json format consisting of nodes and edges of a graph given by a respective agent
        Graph-2 is in a json format consisting of nodes and edges of a graph extracted from an internal database consisting of wrong reasoning
        Score is in an int format consisting of the difference of the two graphs

        You will look at Graph-1 and Graph-2 analyze why graph-2 is wrong and how you can apply to improve graph-1, so it is a more modified educated version
        </context>

        <Example>
        Query - Research the oil price in the market

        Graph - 1 :
        {{
            "nodes": [
                [1, "Research the oil supply/demand"],
                [2, "Research the current OPEC+ production levels"],
                [3, "Analyze global oil inventories"]
            ],
            "edges": [
                [1, 2],
                [2, 3]
            ]
        }}
        Graph 2 : 
        {{
            "nodes": [
                [1, "Check oil production in Texas only"],
                [2, "Ignore global demand data"],
                [3, "Predict prices solely on Texas output"]
            ],
            "edges": [
                [1, 3],
                [2, 3]
            ]
        }}

        Improved Graph 1 :
        {{
            "nodes": [
                [1, "Research the global oil supply and demand balance"],
                [2, "Analyze current OPEC+ production cuts and compliance"],
                [3, "Assess demand trends in China, India, and OECD countries"],
                [4, "Monitor global oil inventories, segmented by OECD/non-OECD"],
                [5, "Evaluate speculative activity in oil futures markets"],
                [6, "Assess macroeconomic indicators influencing oil demand"]
            ],
            "edges": [
                [1, 2],
                [1, 3],
                [1, 4],
                [3, 6],
                [4, 5],
                [2, 4],
                [3, 4],
                [5, 4]
            ]
        }}
        </Example>
        <Graph 1>
        {G1}
        </Graph 1>

        <Graph 2>
        {G2}
        </Graph 2>

        <Score>
        {Score}
        </Score>
        """
        llm = self.llm
        llm = llm.with_structured_output(graphsummary)
        system_prompt = prompt.format(
                G1 = G1,
                G2 = G2,
                Score = score
        )
        result = llm.invoke([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': "Analyze the data"}
        ])
        graph_memory = GraphMemory()
        return result
    
    def visualize_graph(self,G: nx.DiGraph):
        import matplotlib.pyplot as plt
        pos = nx.spring_layout(G)
        labels = nx.get_node_attributes(G, 'text')
        nx.draw(G, pos, with_labels = True, labels = labels)
        plt.show()
    
    def run(self, reasoning):
        nodes_list, edges_list = self.initialize_graph(reasoning)
        G1 = self.build_graph(nodes_list, edges_list)
        compare = 0
        worst_graph = {}

        for data in GraphMemory.extract_data():
            graph = {}
            graph['nodes'] = data['nodes']
            graph['edges'] = data['edges']
            final_graph = self.deserialize_graph(json_str = graph)
            if (self.compare_graphs(G1,final_graph) > compare):
                compare = self.compare_graphs(G1,final_graph)
                worst_graph['nodes'] = data['nodes']
                worst_graph['edges'] = data['edges']
        
        return worst_graph
    



"""
nodes_list = [
    (1, "Collect well test data"),
    (2, "Analyze pressure trends"),
    (3, "Estimate reservoir permeability"),
    (4, "Check for boundary effects"),
    (5, "Summarize well test interpretation")
]

edges_list = [
    (1, 2),
    (2, 3),
    (2, 4),
    (3, 5),
    (4, 5)
]
nodes_list_1 = [
    (1, "Summarize results before analysis"),                  # Bad idea: summarizing too early
    (2, "Collect partial pressure data only"),                 # Incomplete data
    (3, "Guess reservoir behavior based on past tests"),       # Poor assumption
    (4, "Analyze noise in readings before filtering"),         # Wasting time on raw noise
    (5, "Estimate permeability from assumptions"),             # Inference from guesswork
    (6, "Ignore boundary effects for simplicity")              # Ignoring important factors
]

edges_list_1 = [
    (1, 5),   # Jumping to conclusion
    (2, 3),   # Incomplete data leading to guessing
    (3, 5),   # Guess leads to poor estimation
    (2, 4),   # Analyzing before proper filtering
    (4, 1),   # Loop back to summarizing again (redundant)
    (5, 6)    # Leading to oversimplified conclusions
]

# Build and serialize the graph
reasoning_graph = ReasoningGraph()
G1 = reasoning_graph.build_graph(nodes_list, edges_list)
graph_json = reasoning_graph.seralize_graph(G1)

# Example metadata
metadata = {
    "engineer": "TestUser",
    "test_case": "basic well test",
    "timestamp": str(datetime.datetime.now())
}

# Store in memory
graph_memory = GraphMemory()
G2 = reasoning_graph.build_graph(nodes_list_1, edges_list_1)
json_  = reasoning_graph.seralize_graph(G = G2)
graph_memory.short_term_memory(graph_json = json_)




#compare graphs
reasoning_graph = ReasoningGraph()
G1 = reasoning_graph.build_graph(nodes_list, edges_list)
graph_json_1 = reasoning_graph.seralize_graph(G1)
score = reasoning_graph.compare_graphs(G1,G2)
Lesson = reasoning_graph.lesson_agent(graph_json_1,json_,score)

print(Lesson)

"""
