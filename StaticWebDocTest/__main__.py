import os
import StaticWebDoc as module

old_dir = os.curdir 

os.chdir(os.path.split(__file__)[0]) 

runtime = module.Runtime()
runtime.debug()

os.chdir(old_dir)