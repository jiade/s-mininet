This folder contains the S-mininent project source.

scalablelink.py -- coded by Jiade Li
scalablenet.py scalabledemo.py -- coded by Yun Zhu
scalablenode.py and scalableutil.py - coded by Ying Zhang
scalabletop.py -- coded by Jiajun Han
scalablecli.py -- coded by Chang Guo


To run the scalable version:

1. Make sure you have corrected installed the source code.
2. use the command, for example, to run tree topology with scalable version and random placement
sudo -E mn --topo tree,5,2 --cluster localhost,10.227.80.157,10.227.80.158 --placement random
3. use the command, for example, to run linear topology with scalable version and Switchbin (default) placement
sudo -E mn --topo linear,10 --cluster localhost,10.227.80.157,10.227.80.158 


****************
To run the demo that I have created as scalabledemo.py, which is a distributed mininet in two machines, 
You can just:
1, clone a VM and know it's IP by ifconfig
2, step into scalablemininet folder
3, modify the file scalabledemo by changing the remote IP to be IP in step 1.
4, sudo ./scalabledemo
5, do what you like 
