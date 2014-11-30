This folder contains the S-mininent project source.

scalablelink.py -- coded by Jiade Li
scalabledemo.py and scalablemininet.py -- coded by Yun Zhu
scalablenode.py and scalableutil.py - coded by Ying Zhang
scalabletop.py -- coded by Jiajun Han
scalablecli.py -- coded by Chang Guo


To run the scalable version:

1. Make sure you have corrected installed the source code.
2. use the command, for example, to run tree topology with scalable version and random placement
sudo -E mn --topo tree,5,2 --cluster localhost,10.227.80.157,10.227.80.158 --placement random
3. use the command, for example, to run linear topology with scalable version and Switchbin (default) placement
sudo -E mn --topo linear,10 --cluster localhost,10.227.80.157,10.227.80.158 
