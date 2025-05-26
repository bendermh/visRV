# -*- coding: utf-8 -*-
"""
Created on Fri Jun  7 10:06:34 2024

@author: Jorge Rey-Martinez
"""

import pygame as pg
import random

global targetSize
def smoothPursuit(targetSize= "S",x_vel=8,y_vel=2,timeChange=1,totalTime=120,monitor=0):
    #objetcs
    if monitor > pg.display.get_num_displays():
        monitor = 0
        print("Monitor is out of range, autoreset to 0. Detected monitors: " + str(pg.display.get_num_displays()))
    
    main(targetSize= targetSize, x_vel=x_vel,y_vel=y_vel,timeChange=timeChange,totalTime=totalTime,monitor=monitor)
    
class target():
    def __init__(self, targetSize):
        self.screen = pg.display.get_surface()
        self.targetList = ["A","B","E","G","H","J","K","M","P","Q","R","S","T","U","X","Z"]
        self.currentText = random.choice(self.targetList)
        self.center = (self.screen.get_width()//2,self.screen.get_height()//2)
        self.x = self.center[0]
        self.y = self.center[1]
        self.velX = 0
        self.velY = 0
        self.dirX = 1
        self.dirY = 1
        match targetSize:
                
            case "S":
                self.typeSize = 32
                self.radius = 30
                self.border = 5
            case "M":
                self.typeSize = 62
                self.radius = 50
                self.border = 5 
            case "L":
                self.typeSize = 98
                self.radius = 80
                self.border  = 5
            case _:
                self.typeSize = 62
                self.radius = 50
                self.border = 5
                
    def draw(self):          
        self.center = (self.x,self.y)
        self.circle = pg.draw.circle(self.screen, (255,255,255), (self.center), self.radius,width = self.border)
        font = pg.font.SysFont(None, self.typeSize,bold = True)
        self.label = font.render(self.currentText, True, (255,255,255))
        labelPos = self.label.get_rect()
        labelPos.center = self.center
        self.screen.blit(self.label, labelPos)
    
    def move(self, vx,vy):
        self.velX = vx
        self.velY = vy
        if (self.x-self.radius) <= 0 or (self.x+self.radius) >= self.screen.get_width():
            self.dirX *= -1
        if (self.y-self.radius) <= 0 or (self.y+self.radius) >= self.screen.get_height():
            self.dirY *= -1
        self.x += self.dirX*self.velX
        self.y += self.dirY*self.velY
    
    def changeText(self):
        self.currentText = random.choice(self.targetList)
        print("Target: " + self.currentText)



def main(targetSize= "S",x_vel=8,y_vel=2,timeChange=1,totalTime=120,monitor=0):
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
    game_target = target(targetSize)
    
    #prepare loop and timers-event
    going = True
    clock = pg.time.Clock()
    TEXTCHANGE_EVENT = pg.USEREVENT + 1
    pg.time.set_timer(TEXTCHANGE_EVENT,(round(timeChange*10)*100))
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
            if event.type == TEXTCHANGE_EVENT:
                game_target.changeText()
            
        pg.display.flip()
        screen.blit(background, (0, 0))
        game_target.move(x_vel, y_vel)
        game_target.draw()
    pg.quit()
    print("Excercise finished. Bye !")
    
#for testing purposes
if __name__ == "__main__":
    smoothPursuit()