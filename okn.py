# -*- coding: utf-8 -*-
"""
Created on Fri Jun  7 10:06:34 2024

@author: Jorge Rey-Martinez
"""

import pygame as pg

global targetSize
def okn(targetSize= "L",vel=20,direction="D",totalTime=120,monitor=0):
    #objetcs
    if monitor > pg.display.get_num_displays():
        monitor = 0
        print("Monitor is out of range, autoreset to 0. Detected monitors: " + str(pg.display.get_num_displays()))
        
    match targetSize:
               
        case "S":
            ts = 120
        case "M":
            ts = 160
        case "L":
            ts  = 240
        case _:
            ts = 240
        
    if vel >= ts//2:
        vel =  ts//2
        print("Velocity reset to: " +str(vel))
    
    main(targetSize= ts,vel=vel,direction=direction,totalTime=totalTime,monitor=monitor)
    
class target():
    def __init__(self, targetSize,direction):
        self.screen = pg.display.get_surface()
        self.dir = direction
        self.bars = []
        self.border = targetSize
                
        self.generate()
        
    
    def generate(self):
        if self.dir == "R" or self.dir == "L":
            if self.dir =="R":
                self.bars.append(pg.Rect((0-self.border),0,self.border,self.screen.get_height()))
            else:
                self.bars.append(pg.Rect((self.screen.get_width()+self.border),0,self.border,self.screen.get_height()))
        else:
            if self.dir =="U":
                self.bars.append(pg.Rect((0,(self.screen.get_height()+self.border),self.screen.get_width(),self.border)))
            else:
                self.bars.append(pg.Rect((0,(0-self.border),self.screen.get_width(),self.border)))
                
    
    def draw(self,veloc):
        for bar in self.bars:
            firstDelete = True;
            toAdd = []
            if self.dir == "R" or self.dir == "L":
                if self.dir =="R":
                    if bar.x < self.screen.get_width():
                        bar.x += veloc
                    else:
                        if firstDelete:
                            firstDelete = False
                            self.bars.pop(0)
                            self.bars[0].x += veloc 
                    if bar.x >= self.border:
                        toAdd.append(bar)
                
                else:
                    if bar.x > (0-self.border):
                        bar.x -= veloc
                    else:
                        if firstDelete:
                            firstDelete = False
                            self.bars.pop(0)
                            self.bars[0].x -= veloc
                    if bar.x <= self.screen.get_width()-self.border:
                        toAdd.append(bar)
            else:
                if self.dir == "U":
                    if bar.y > (0-self.border):
                        bar.y -= veloc
                    else:
                        if firstDelete:
                            firstDelete = False
                            self.bars.pop(0)
                            self.bars[0].y -= veloc 
                    if bar.y <= (self.screen.get_height()-self.border):
                        toAdd.append(bar)
                
                else:
                    if bar.y >= 0-self.border:
                        bar.y += veloc
                    else:
                        if firstDelete:
                            firstDelete = False
                            self.bars.pop(0)
                            self.bars[0].y += veloc
                    if bar.y >= self.border:
                        toAdd.append(bar)
                    
        if len(toAdd) > 0 :
            self.generate()
            toAdd = []
            
        for bar in self.bars:
            pg.draw.rect(self.screen, (255,255,255),bar)
        pg.display.flip()
        

def main(targetSize,vel,direction,totalTime,monitor):
    pg.init()
    screen = pg.display.set_mode(size=(1920,1080), flags= pg.FULLSCREEN|pg.NOFRAME|pg.DOUBLEBUF, display= monitor, vsync= 1)
    screen.fill(color=(0,0,0))
    fps = 60
    pg.mouse.set_visible(False)
    #background
    background = pg.Surface(screen.get_size())
    background = background.convert()
    background.fill((0, 0, 0))
    
    # Display The Background
    screen.blit(background, (0, 0))
    #clock = pg.time.Clock()
    
    #prepare objects
    barsGame = target(targetSize, direction)

    
    #prepare loop and timers-event
    going = True
    clock = pg.time.Clock()
    pg.time.set_timer(pg.QUIT,(totalTime*1000),1)

    while going:
        clock.tick(fps)
        going = True
        # Handle Input Events
        for event in pg.event.get():
            if event.type == pg.QUIT:
                going = False
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_ESCAPE:
                    going = False
        screen.blit(background, (0, 0))
        barsGame.draw(vel)
    pg.quit()
    print("Excercise finished. Bye !")
    
#for testing purposes
if __name__ == "__main__":
    okn()