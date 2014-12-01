#!/usr/bin/python
"""
scalablenode.py

This file is an externsion of mininet/node.py. It is the super class 
for host, switch controller modules. It defines the interface for
remote hosts, switches, and controllers.  
The communications among remote nodes are through ssh tunnel

Contributor: Ying Zhang
"""

from mininet.node import Node, Host, OVSSwitch, Controller
from mininet.link import Link, Intf
from mininet.net import Mininet
from mininet.topo import LinearTopo
from mininet.topolib import TreeTopo
from mininet.util import quietRun, makeIntfPair, errRun, retry
from mininet.scalablemininet.scalablecli import CLI
from mininet.log import setLogLevel, debug, info, error

from mininet.scalablemininet.scalablecli import CLI

from signal import signal, SIGINT, SIG_IGN
from subprocess import Popen, PIPE, STDOUT
import os
from random import randrange
from sys import exit
import re

from distutils.version import StrictVersion

class RemoteMixin( object ):
    # Super class for all types of nodes
    # define ssh options

    sshbase = [ 'ssh', '-q',
                '-o', 'BatchMode=yes',
                '-o', 'ForwardAgent=yes', '-tt' ]

    # initialize a remote node with node name, and remote server, IP, controlPath, optional

    def __init__( self, name, server='localhost', user=None, serverIP=None,
                  controlPath=False, splitInit=False, **kwargs):
        # If it is a remote server, connect using IP address
        self.server = server if server else 'localhost'
        self.serverIP = serverIP if serverIP else self.findServerIP( self.server )
        self.user = user if user else self.findUser()

        if controlPath is True:
            # Set a default control path for shared SSH connections
            controlPath = '/tmp/mn-%r@%h:%p'
        self.controlPath = controlPath
        self.splitInit = splitInit

        # if remote server, set the destination IP address and the controlpath
        if self.user and self.server != 'localhost':
            self.dest = '%s@%s' % ( self.user, self.serverIP )
            self.sshcmd = [ 'sudo', '-E', '-u', self.user ] + self.sshbase
            if self.controlPath:
                self.sshcmd += [ '-o', 'ControlPath=' + self.controlPath,
                                 '-o', 'ControlMaster=auto' ]
            self.sshcmd = self.sshcmd + [ self.dest ]
            self.isRemote = True
        else:
            self.dest = None
            self.sshcmd = []
            self.isRemote = False
        super( RemoteMixin, self ).__init__( name, **kwargs )

    @staticmethod
    def findUser():
        "Try to return logged-in (usually non-root) user"
        try:
            # If we're running sudo
            return os.environ[ 'SUDO_USER' ]
        except:
            try:
                # Logged-in user (if we have a tty)
                return quietRun( 'who am i' ).split()[ 0 ]
            except:
                # Give up and return effective user
                return quietRun( 'whoami' )

    # Determine IP address of local host
    _ipMatchRegex = re.compile( r'\d+\.\d+\.\d+\.\d+' )

    @classmethod
    def findServerIP( cls, server ):
        "Return our server's IP address"
        # If we can match the IP
        ipmatch = cls._ipMatchRegex.findall( server )
        if ipmatch:
            return ipmatch[ 0 ]
        # Otherwise, look up remote server
        output = quietRun( 'getent ahostsv4 %s' % server )
        ips = cls._ipMatchRegex.findall( output )
        ip = ips[ 0 ] if ips else None
        return ip

    # Start user-level shell process, if it is remote host, start remote process
    def startShell( self, *args, **kwargs ):
        "Start a shell process for running commands"
        if self.isRemote:
            kwargs.update( mnopts='-c' )
        super( RemoteMixin, self ).startShell( *args, **kwargs )
        if self.splitInit:
            self.sendCmd( 'echo $$' )
        else:
            self.pid = int( self.cmd( 'echo $$' ) )

    def finishInit( self ):
        self.pid = int( self.waitOutput() )

    def rpopen( self, *cmd, **opts ):
        "Return a Popen object on underlying server in root namespace"
        params = { 'stdin': PIPE,
                   'stdout': PIPE,
                   'stderr': STDOUT,
                   'sudo': True }
        params.update( opts )
        return self._popen( *cmd, **params )

    def rcmd( self, *cmd, **opts):
        # Interface for user command with options, using system command popen
        popen = self.rpopen( *cmd, **opts )
        result = ''
        while True:
            poll = popen.poll()
            result += popen.stdout.read()
            if poll is not None:
                break
        return result

    @staticmethod
    def _ignoreSignal():
        "Detach from process group to ignore all signals"
        os.setpgrp()

    def _popen( self, cmd, sudo=True, tt=True, **params):
        # Initiate a process on on remote node with the command and options
        if type( cmd ) is str:
            cmd = cmd.split()
        if self.isRemote:
            if sudo:
                cmd = [ 'sudo', '-E' ] + cmd
            if tt:
                cmd = self.sshcmd + cmd
            else:
                sshcmd = list( self.sshcmd )
                sshcmd.remove( '-tt' )
                cmd = sshcmd + cmd
        else:
            if self.user and not sudo:
                # Drop privileges
                cmd = [ 'sudo', '-E', '-u', self.user ] + cmd
        params.update( preexec_fn=self._ignoreSignal )
        debug( '_popen', ' '.join(cmd), params )
        popen = super( RemoteMixin, self )._popen( cmd, **params )
        return popen

    def popen( self, *args, **kwargs ):
        "Override: disable -tt"
        return super( RemoteMixin, self).popen( *args, tt=False, **kwargs )

    def addIntf( self, *args, **kwargs ):
        "Override: use RemoteLink.moveIntf"
        return super( RemoteMixin, self).addIntf( *args,
                        moveIntfFn=RemoteLink.moveIntf, **kwargs )


class RemoteNode( RemoteMixin, Node ):
    "A node on a remote server"
    pass


class RemoteHost( RemoteNode ):
    "A RemoteHost is simply a RemoteNode"
    pass


class RemoteOVSSwitch( RemoteMixin, OVSSwitch ):
    "Remote instance of Open vSwitch"
    OVSVersions = {}
    def isOldOVS( self ):
        "Is remote switch using an old OVS version?"
        cls = type( self )
        if self.server not in cls.OVSVersions:
            vers = self.cmd( 'ovs-vsctl --version' )
            cls.OVSVersions[ self.server ] = re.findall( '\d+\.\d+', vers )[ 0 ]
        return ( StrictVersion( cls.OVSVersions[ self.server ] ) <
                StrictVersion( '1.10' ) )

if __name__ == '__main__':
    setLogLevel( 'info' )
    signalTest()
