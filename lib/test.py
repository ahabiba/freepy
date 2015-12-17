import os

cwd = os.path.dirname(os.path.realpath(__file__))
cwd = os.path.dirname(cwd)
print os.path.join(cwd, 'switchlets')