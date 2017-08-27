
from ..base import *
import networkx as nx 
import angr
import itertools

class AngrCallstackKeyClusterer(Clusterer):
    def __init__(self, visible=True):
        super(AngrCallstackKeyClusterer, self).__init__()
        self.visible = visible

    def cluster(self, graph):
        
        for node in graph.nodes:
            key = node.obj.callstack_key
            cluster = graph.get_cluster(key)
            if not cluster:
                cluster = graph.create_cluster(key, visible=self.visible)
            cluster.add_node(node)

        # merge by jump edges
        jgraph = nx.DiGraph()
        for e in graph.edges:
            if e.src.cluster and e.dst.cluster and e.src.cluster != e.dst.cluster:
                if  e.meta['jumpkind'] == 'Ijk_Boring':
                    jgraph.add_edge(e.src.cluster.key, e.dst.cluster.key)
        
        for n in jgraph.nodes():
            in_edges = jgraph.in_edges(n)
            if len(in_edges) == 1:
                s,t = in_edges[0]
                scluster = graph.get_cluster(s)
                for n in graph.nodes:
                    if n.cluster.key == t:
                        n.cluster.remove_node(n)
                        scluster.add_node(n)

        # build cluster hierarchy
        cgraph = nx.DiGraph()
        for e in graph.edges:
            if e.src.cluster and e.dst.cluster and e.src.cluster != e.dst.cluster:
                if  e.meta['jumpkind'] == 'Ijk_Call':
                    cgraph.add_edge(e.src.cluster.key, e.dst.cluster.key)
        
        for n in cgraph.nodes():
            in_edges = cgraph.in_edges(n)
            if len(in_edges) == 1:
                s,t = in_edges[0]
                scluster = graph.get_cluster(s)
                tcluster = graph.get_cluster(t)
                tcluster.parent = scluster


class AngrStructuredClusterer(Clusterer):
    def __init__(self, struct):
        super(AngrStructuredClusterer, self).__init__()
        self.struct = struct
        self.block_to_cluster = {}
        self.seq = itertools.count()
        
    def build(self, obj, graph, parent_cluster):
        if isinstance(obj, angr.analyses.region_identifier.GraphRegion):
            cluster = graph.create_cluster(str(self.seq.next()), parent=parent_cluster, label=repr(obj))
            for n in obj.graph.nodes():
                self.build(n, graph, cluster)
        elif isinstance(obj, angr.analyses.region_identifier.MultiNode):
            cluster = graph.create_cluster(str(self.seq.next()), parent=parent_cluster, label=repr(obj))
            for n in obj.nodes:
                self.build(n, graph, cluster)
        elif isinstance(obj, angr.analyses.structurer.SequenceNode):
            cluster = graph.create_cluster(str(self.seq.next()), parent=parent_cluster, label=repr(obj))    
            for n in obj.nodes:
                self.build(n, graph, cluster)
        elif isinstance(obj, angr.analyses.structurer.CodeNode):
            cluster = graph.create_cluster(str(self.seq.next()), parent=parent_cluster, label=["CODE NODE 0x%x" % obj.addr, "Reaching condition: %s" % obj.reaching_condition]) 
            self.build(obj.node, graph, cluster)
        elif isinstance(obj, angr.analyses.structurer.LoopNode):
            cluster = graph.create_cluster(str(self.seq.next()), parent=parent_cluster, label=["LOOP NODE 0x%x" % obj.addr, "Condition:  %s" % obj.condition])
            self.build(obj.sequence_node, graph, cluster)
        elif isinstance(obj, angr.analyses.structurer.ConditionNode):
            cluster = graph.create_cluster(str(self.seq.next()), parent=parent_cluster, label=["CONDITION NODE 0x%x" % obj.addr, "Condition:  %s" % obj.condition, "Reaching condition: %s" % obj.reaching_condition])
            if obj.true_node:
                self.build(obj.true_node, graph, cluster)
            if obj.false_node:
                self.build(obj.false_node, graph, cluster)
        elif isinstance(obj, angr.analyses.structurer.BreakNode):
            cluster = graph.create_cluster(str(self.seq.next()), parent=parent_cluster, label=["BREAK NODE"])
            self.build(obj.target, graph, cluster)
        elif isinstance(obj, angr.analyses.structurer.ConditionalBreakNode):
            cluster = graph.create_cluster(str(self.seq.next()), parent=parent_cluster, label=["CONDITIONAL BREAK NODE", "Condition:  %s" % obj.condition])
            self.build(obj.target, graph, cluster)
        elif type(obj).__name__ == 'Block':
            self.block_to_cluster[obj] = parent_cluster
        elif isinstance(obj, nx.DiGraph):
            for n in obj.nodes():
                self.build(n, graph, parent_cluster)
        else:
            print type(obj)
            import ipdb; ipdb.set_trace()

    def cluster(self, graph):
        self.build(self.struct, graph, None)
        to_remove = []
        
        for n in graph.nodes:
            if n.obj in self.block_to_cluster:
                cluster = self.block_to_cluster[n.obj]
                if cluster:
                    cluster.add_node(n)
            else:
                to_remove.append(n)
        
        #for n in to_remove:
        #    graph.remove_node(n)
                
