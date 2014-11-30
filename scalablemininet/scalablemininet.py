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


class MininetCluster( Mininet ):

    "scalable version of Mininet class"
    '''
    in our scheme, we use ssh to build the scalable mininet. 
    The functionality of MininetCluster is to build up the topology
    To place host and switches in different servers, he stragedy of different place method should be proposed.
    And this class will use different placer. 
 
    '''

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
	#merge two dictionary
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
        #run the super class initialazation and build the toplogy in that function
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
      '''this is the key function. '''
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

