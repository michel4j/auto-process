'''
Created on Mar 24, 2011

@author: michel
'''
import pwd

def get_project_name():
    return pwd.getpwuid(os.geteuid())[0]

def get_home_dir():
    return pwd.getpwuid(os.geteuid())[5]
    
