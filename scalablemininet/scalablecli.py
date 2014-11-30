__author__ = 'changguo'

#!/usr/bin/python

"CLI for Scalable Mininet prototype"

from mininet.cli import CLI
from mininet.log import output, error

nx, graphviz_layout, plt = None, None, None  # Will be imported on demand


class DemoCLI( CLI ):
    "CLI with additional commands for Scalable Mininet"

    @staticmethod
    def colorsFor( seq ):
        "Information of background colors for a sequence"
        colors = [ 'red', 'lightgreen', 'cyan', 'yellow', 'orange',
                  'magenta', 'pink', 'grey', 'brown',
                  'white' ]
        sequencelen, colorslen = len( seq ), len( colors )
        reps = max( 1, sequencelen / colorslen )
        colors = colors * reps
        colors = colors[ 0 : sequencelen ]
        return colors
    
    def do_plot( self, line ):
        "Plot topology colored by node placement"
        global nx, plt
        if not nx:
            try:
                import networkx as nx
                import matplotlib.pyplot as plt
                import pygraphviz
            except:
                error( 'plot requires networkx, matplotlib and pygraphviz - '
                       'please install them and try again\n' )
                return
        # Build a network graph
        graph = nx.Graph()
        mn = self.mn
        servers, hosts, switches = mn.servers, mn.hosts, mn.switches
        hostlen, switchlen = len( hosts ), len( switches )
        nodes = hosts + switches
        graph.add_nodes_from( nodes )
        links = [ ( link.intf1.node, link.intf2.node )
                  for link in self.mn.links ]
        graph.add_edges_from( links )
        # shapes = hostlen * [ 's' ] + switchlen * [ 'o' ]
        color = dict( zip( servers, self.colorsFor( servers ) ) )    # Plot graph using selected colors
        pos = nx.graphviz_layout( graph )
        opts = { 'ax': None, 'font_weight': 'bold',
		 'width': 2, 'edge_color': 'darkblue' }
        hostcolors = [ color[ getattr( h, 'server', 'localhost' ) ] for h in hosts ]
        switchcolors = [ color[ getattr( s, 'server', 'localhost' ) ] for s in switches ]
        nx.draw_networkx( graph, pos=pos, nodelist=hosts, node_size=800, label='host',
                          node_color=hostcolors, node_shape='s', **opts )
        nx.draw_networkx( graph, pos=pos, nodelist=switches, node_size=1000,
                          node_color=switchcolors, node_shape='o', **opts )
        # Plot the whole graph
        fig = plt.gcf()
        ax = plt.gca()
        ax.get_xaxis().set_visible( False )
        ax.get_yaxis().set_visible( False )
        fig.canvas.set_window_title( 'Mininet')
        plt.title( 'Node Placement', fontweight='bold' )
        plt.show()

    def do_status( self, line ):
        nodes = self.mn.hosts + self.mn.switches
        for node in nodes:
            node.shell.poll()
        exited = [ node for node in nodes
                   if node.shell.returncode is not None ]
        if exited:
            for node in exited:
                output( '%s has exited with code %d\n'
                        % ( node, node.shell.returncode ) )
        else:
            output( 'All nodes are still running.\n' )


    def do_placement( self, line ):         
        mn = self.mn
        nodes = mn.hosts + mn.switches + mn.controllers
        for server in mn.servers:
            names = [ n.name for n in nodes if hasattr( n, 'server' )
                      and n.server == server ]
            output( '%s: %s\n' % ( server, ' '.join( names ) ) )
