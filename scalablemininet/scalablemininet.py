#!/usr/bin/python
'''
add by Yun Zhu
This is the main class for scalable mininet
The function is to build up the net according to topology information
'''

from mininet.node import Node, Host, OVSSwitch, Controller
from mininet.link import Link, Intf
from mininet.net import Mininet
from mininet.topo import LinearTopo
from mininet.topolib import TreeTopo
from mininet.util import quietRun, makeIntfPair, errRun, retry
from mininet.examples.clustercli import CLI
from mininet.log import setLogLevel, debug, info, error

from signal import signal, SIGINT, SIG_IGN
from subprocess import Popen, PIPE, STDOUT
import os
from random import randrange
from sys import exit
import re

from distutils.version import StrictVersion


class Placer( object ):
    "Node placement algorithm for MininetCluster"

    def __init__( self, servers=None, nodes=None, hosts=None,
                 switches=None, controllers=None, links=None ):
        """Initialize placement object
           servers: list of servers
           nodes: list of all nodes
           hosts: list of hosts
           switches: list of switches
           controllers: list of controllers
           links: list of links
           (all arguments are optional)
           returns: server"""
        self.servers = servers or []
        self.nodes = nodes or []
        self.hosts = hosts or []
        self.switches = switches or []
        self.controllers = controllers or []
        self.links = links or []

    def place( self, node ):
        "Return server for a given node"
        # Default placement: run locally
        return None


class RandomPlacer( Placer ):
    "Random placement"
    def place( self, nodename ):
        """Random placement function
            nodename: node name"""
        # This may be slow with lots of servers
        return self.servers[ randrange( 0, len( self.servers ) ) ]


class RoundRobinPlacer( Placer ):
    """Round-robin placement
       Note this will usually result in cross-server links between
       hosts and switches"""

    def __init__( self, *args, **kwargs ):
        Placer.__init__( self, *args, **kwargs )
        self.next = 0

    def place( self, nodename ):
        """Round-robin placement function
            nodename: node name"""
        # This may be slow with lots of servers
        server = self.servers[ self.next ]
        self.next = ( self.next + 1 ) % len( self.servers )
        return server


class SwitchBinPlacer( Placer ):
    """Place switches (and controllers) into evenly-sized bins,
       and attempt to co-locate hosts and switches"""

    def __init__( self, *args, **kwargs ):
        Placer.__init__( self, *args, **kwargs )
        # Easy lookup for servers and node sets
        self.servdict = dict( enumerate( self.servers ) )
        self.hset = frozenset( self.hosts )
        self.sset = frozenset( self.switches )
        self.cset = frozenset( self.controllers )
        # Server and switch placement indices
        self.placement =  self.calculatePlacement()

    @staticmethod
    def bin( nodes, servers ):
        "Distribute nodes evenly over servers"
        # Calculate base bin size
        nlen = len( nodes )
        slen = len( servers )
        # Basic bin size
        quotient = int( nlen / slen )
        binsizes = { server: quotient for server in servers }
        # Distribute remainder
        remainder = nlen % slen
        for server in servers[ 0 : remainder ]:
            binsizes[ server ] += 1
        # Create binsize[ server ] tickets for each server
        tickets = sum( [ binsizes[ server ] * [ server ]
                         for server in servers ], [] )
        # And assign one ticket to each node
        return { node: ticket for node, ticket in zip( nodes, tickets ) }

    def calculatePlacement( self ):
        "Pre-calculate node placement"
        placement = {}
        # Create host-switch connectivity map,
        # associating host with last switch that it's
        # connected to
        switchFor = {}
        for src, dst in self.links:
            if src in self.hset and dst in self.sset:
                switchFor[ src ] = dst
            if dst in self.hset and src in self.sset:
                switchFor[ dst ] = src
        # Place switches
        placement = self.bin( self.switches, self.servers )
        # Place controllers and merge into placement dict
        placement.update( self.bin( self.controllers, self.servers ) )
        # Co-locate hosts with their switches
        for h in self.hosts:
            if h in placement:
                # Host is already placed - leave it there
                continue
            if h in switchFor:
                placement[ h ] = placement[ switchFor[ h ] ]
            else:
                raise Exception(
                        "SwitchBinPlacer: cannot place isolated host " + h )
        return placement

    def place( self, node ):
        """Simple placement algorithm:
           place switches into evenly sized bins,
           and place hosts near their switches"""
        return self.placement[ node ]


class HostSwitchBinPlacer( Placer ):
    """Place switches *and hosts* into evenly-sized bins
       Note that this will usually result in cross-server
       links between hosts and switches"""

    def __init__( self, *args, **kwargs ):
        Placer.__init__( self, *args, **kwargs )
        # Calculate bin sizes
        scount = len( self.servers )
        self.hbin = max( int( len( self.hosts ) / scount ), 1 )
        self.sbin = max( int( len( self.switches ) / scount ), 1 )
        self.cbin = max( int( len( self.controllers ) / scount ) , 1 )
        info( 'scount:', scount )
        info( 'bins:', self.hbin, self.sbin, self.cbin, '\n' )
        self.servdict = dict( enumerate( self.servers ) )
        self.hset = frozenset( self.hosts )
        self.sset = frozenset( self.switches )
        self.cset = frozenset( self.controllers )
        self.hind, self.sind, self.cind = 0, 0, 0

    def place( self, nodename ):
        """Simple placement algorithm:
            place nodes into evenly sized bins"""
        # Place nodes into bins
        if nodename in self.hset:
            server = self.servdict[ self.hind / self.hbin ]
            self.hind += 1
        elif nodename in self.sset:
            server = self.servdict[ self.sind / self.sbin ]
            self.sind += 1
        elif nodename in self.cset:
            server = self.servdict[ self.cind / self.cbin ]
            self.cind += 1
        else:
            info( 'warning: unknown node', nodename )
            server = self.servdict[ 0 ]
        return server


class MininetCluster( Mininet ):

    "Cluster-enhanced version of Mininet class"

    # Default ssh command
    # BatchMode yes: don't ask for password
    # ForwardAgent yes: forward authentication credentials
    sshcmd = [ 'ssh', '-o', 'BatchMode=yes', '-o', 'ForwardAgent=yes' ]

    def __init__( self, *args, **kwargs ):
        """servers: a list of servers to use (note: include
           localhost or None to use local system as well)
           user: user name for server ssh
           placement: Placer() subclass"""
        params = { 'host': RemoteHost,
                   'switch': RemoteOVSSwitch,
                   'link': RemoteLink,
                   'precheck': True }
        params.update( kwargs )
        servers = params.pop( 'servers', [ 'localhost' ] )
        servers = [ s if s else 'localhost' for s in servers ]
        self.servers = servers
        self.serverIP = params.pop( 'serverIP', {} )
        if not self.serverIP:
            self.serverIP = { server: RemoteMixin.findServerIP( server )
                              for server in self.servers }
        self.user = params.pop( 'user', RemoteMixin.findUser() )
        if params.pop( 'precheck' ):
            self.precheck()
        self.connections = {}
        self.placement = params.pop( 'placement', SwitchBinPlacer )
        # Make sure control directory exists
        self.cdir = os.environ[ 'HOME' ] + '/.ssh/mn'
        errRun( [ 'mkdir', '-p', self.cdir ] )
        Mininet.__init__( self, *args, **params )

    def popen( self, cmd ):
        "Popen() for server connections"
        old = signal( SIGINT, SIG_IGN )
        conn = Popen( cmd, stdin=PIPE, stdout=PIPE, close_fds=True )
        signal( SIGINT, old )
        return conn

    def baddLink( self, *args, **kwargs ):
        "break addlink for testing"
        pass

    def precheck( self ):
        """Pre-check to make sure connection works and that
           we can call sudo without a password"""
        result = 0
        info( '*** Checking servers\n' )
        for server in self.servers:
            ip = self.serverIP[ server ]
            if not server or server == 'localhost':
                 continue
            info( server, '' )
            dest = '%s@%s' % ( self.user, ip )
            cmd = [ 'sudo', '-E', '-u', self.user ]
            cmd += self.sshcmd + [ '-n', dest, 'sudo true' ]
            debug( ' '.join( cmd ), '\n' )
            out, err, code = errRun( cmd )
            if code != 0:
                error( '\nstartConnection: server connection check failed '
                       'to %s using command:\n%s\n'
                        % ( server, ' '.join( cmd ) ) )
            result |= code
        if result:
            error( '*** Server precheck failed.\n'
                   '*** Make sure that the above ssh command works correctly.\n'
                   '*** You may also need to run mn -c on all nodes, and/or\n'
                   '*** use sudo -E.\n' )
            exit( 1 )
        info( '\n' )

    def modifiedaddHost( self, *args, **kwargs ):
        "Slightly modify addHost"
        kwargs[ 'splitInit' ] = True
        return Mininet.addHost( *args, **kwargs )


    def placeNodes( self ):
        """Place nodes on servers (if they don't have a server), and
           start shell processes"""
        if not self.servers or not self.topo:
            # No shirt, no shoes, no service
            return
        nodes = self.topo.nodes()
        placer = self.placement( servers=self.servers,
                                 nodes=self.topo.nodes(),
                                 hosts=self.topo.hosts(),
                                 switches=self.topo.switches(),
                                 links=self.topo.links() )
        for node in nodes:
            config = self.topo.nodeInfo( node )
            # keep local server name consistent accross nodes
            if 'server' in config.keys() and config[ 'server' ] == None:
                config[ 'server' ] = 'localhost'
            server = config.setdefault( 'server', placer.place( node ) )
            if server:
                config.setdefault( 'serverIP', self.serverIP[ server ] )
            info( '%s:%s ' % ( node, server ) )
            key = ( None, server )
            _dest, cfile, _conn = self.connections.get(
                        key, ( None, None, None ) )
            if cfile:
                config.setdefault( 'controlPath', cfile )

    def addController( self, *args, **kwargs ):
        "Patch to update IP address to global IP address"
        controller = Mininet.addController( self, *args, **kwargs )
        # Update IP address for controller that may not be local
        if ( isinstance( controller, Controller)
             and controller.IP() == '127.0.0.1'
             and ' eth0:' in controller.cmd( 'ip link show' ) ):
             Intf( 'eth0', node=controller ).updateIP()
        return controller

    def buildFromTopo( self, *args, **kwargs ):
        "Start network"
        info( '*** Placing nodes\n' )
        self.placeNodes()
        info( '\n' )
        Mininet.buildFromTopo( self, *args, **kwargs )

