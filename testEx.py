# -*- coding: utf-8 -*-
"""
Created on Tue Jun  4 14:18:06 2024

@author: Hospital Donostia
"""

import smoothPursuit
import pyglet

app = smoothPursuit.smoothPursuit(targetSize= "S",x_vel=8,y_vel=2,timeChange=1,totalTime=120,monitor=0)
pyglet.app.run()