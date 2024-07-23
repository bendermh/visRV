# -*- coding: utf-8 -*-
"""
Created on Fri Jun  7 10:06:34 2024

@author: Hospital Donostia
"""

import pygame as pg
from mbientlab.metawear import MetaWear,libmetawear, parse_value
from mbientlab.metawear.cbindings import *
from mbientlab.warble import * 
from scipy.spatial.transform import Rotation
import time

def vor(targetSize= "L",macIMU="C7:0F:6B:58:F9:CB", vorTrain = True, vRange = 10, hRange = 20, totalTime=120,monitor=0):
    #objetcs
    if monitor > pg.display.get_num_displays():
        monitor = 0
        print("Monitor is out of range, autoreset to 0")
        
    match targetSize:
               
        case "S":
            ts = 120
        case "M":
            ts = 160
        case "L":
            ts  = 240
        case _:
            ts = 240
    
    main(targetSize= ts,mac = macIMU, vorTrain = vorTrain, vRange=vRange, hRange = hRange, totalTime=totalTime,monitor=monitor)
    
class target():
    def __init__(self,targetSize,mac,vorTrain, vRange, hRange):
        self.screen = pg.display.get_surface()
        self.imuDevice = MetaWear(mac)
        self.reverse = vorTrain
        self.readIMU = FnVoid_VoidP_DataP(self.streamIMU)
        self.timeConnect = None 
        self.timeLast = None
        self.signal = None
        self.sample = None
        self.headPositionH = None # 90 Deg is button and led in the bottom and looking at examiners positioned on the back head of participant
        self.headPositionV = None
        self.biasH = 0 #to modify if accelerometer is not accurate
        self.biasV = 0
        self.samplingInterval = 0.01 # minimum time in secs to read IMU data 0.01 are 65Hz aprox
        self.timeIMUSetup = 2.1 # delay in seconds to stream data to avoid IMU setup empty samples
        self.screenPositionH = 0
        self.screenPositionV = 0
        self.headRangeH = hRange #half head range movement
        self.headRangeV = vRange
        self.screenMaxH = self.screen.get_width()
        self.screenMaxV = self.screen.get_height()
        self.timeConnect = time.time() 
        self.timeLast = time.time()
        
        try:
            self.imuDevice.connect()
            time.sleep(3)
            self.isConected = True
            print("IMU connected, setting Up")
            self.configureIMU()
            
        except:
            self.isConected = False
            print("IMU connection error")
        
                
    
    def draw(self):
        pass
    
    def configureIMU(self):
        print("Setting up IMU...")
        # confiure connection
        libmetawear.mbl_mw_settings_set_connection_parameters(self.imuDevice.board, 7.5, 7.5, 0, 6000)
        time.sleep(1.5)
        # setup quaternion
        libmetawear.mbl_mw_sensor_fusion_set_mode(self.imuDevice.board, SensorFusionMode.NDOF);
        libmetawear.mbl_mw_sensor_fusion_set_acc_range(self.imuDevice.board, SensorFusionAccRange._4G)
        libmetawear.mbl_mw_sensor_fusion_set_gyro_range(self.imuDevice.board, SensorFusionGyroRange._2000DPS)
        libmetawear.mbl_mw_sensor_fusion_write_config(self.imuDevice.board)
        time.sleep(0.5)
        # get quat signal and subscribe
        self.signal = libmetawear.mbl_mw_sensor_fusion_get_data_signal(self.imuDevice.board, SensorFusionData.EULER_ANGLE);
        libmetawear.mbl_mw_datasignal_subscribe(self.signal, None, self.readIMU)
        # start acc, gyro, mag
        libmetawear.mbl_mw_sensor_fusion_enable_data(self.imuDevice.board, SensorFusionData.EULER_ANGLE);
        libmetawear.mbl_mw_sensor_fusion_start(self.imuDevice.board);
        print("IMU setup done.")
        time.sleep(0.25)

    def streamIMU(self, ctx, data):
        timeNow = time.time()
        if (timeNow-self.timeLast) > self.samplingInterval: 
            if self.isConected:
                if (self.timeLast-self.timeConnect) > self.timeIMUSetup: # add a little delay to stream data to avoid setup empty samples
                    euler = parse_value(data)
                    self.sample = ((self.timeLast-self.timeConnect)-self.timeIMUSetup,euler)
            self.timeLast = time.time()
            self.headPositionH = round(self.sample[1].yaw + 90.0)
            self.headPositionV = round(self.sample[1].pitch*-1)
    
            if self.headPositionH > 360:
                self.headPositionH -= 360
           
            self.headPositionH += self.biasH
            self.headPositionV += self.biasV
            
            if self.headPositionH < 90-self.headRangeH:
                self.headPositionH = 90-self.headRangeH
            
            if self.headPositionH > 90+self.headRangeH:
                self.headPositionH = 90+self.headRangeH
                
            if self.headPositionV < 90-self.headRangeV:
                self.headPositionV = 90-self.headRangeV
            
            if self.headPositionV > 90+self.headRangeV:
                self.headPositionV = 90+self.headRangeV
            
            self.screenPositionH = self.angleToScreen(self.headPositionH, (90 - self.headRangeH), (90 + self.headRangeH), 0, self.screenMaxH, self.reverse)
            self.screenPositionV = self.angleToScreen(self.headPositionV, (90 - self.headRangeV), (90 + self.headRangeV), 0, self.screenMaxV, not self.reverse)
    
    def angleToScreen(self,angle,angleMin,angleMax,screenMin,screenMax,inverse = True):
        if inverse:
            return round(screenMax-(screenMin+(float(angle-angleMin)/float(angleMax-angleMin)*(screenMax-screenMin))))
        else:
            return round(screenMin+(float(angle-angleMin)/float(angleMax-angleMin)*(screenMax-screenMin)))
    
    def safeIMUDisconnect(self):    
        if self.isConected:
                    print("Closing IMU connection...")
                    #stop
                    libmetawear.mbl_mw_sensor_fusion_stop(self.imuDevice.board)
                    libmetawear.mbl_mw_datasignal_unsubscribe(self.signal)
                    time.sleep(0.5)
                    # disconnect
                    self.imuDevice.disconnect()
                    time.sleep(3)
                    self.isConected = False
                    print("IMU connection closed")
                    
        else:
                    print("No IMU connection to close")    


def main(targetSize,mac,vorTrain,vRange,hRange,totalTime,monitor):
    pg.init()
    screen = pg.display.set_mode(size=(1920,1080), flags= pg.FULLSCREEN|pg.NOFRAME|pg.DOUBLEBUF, display= monitor, vsync= 1)
    screen.fill(color=(0,0,0))
    fps = 60
    #background
    background = pg.Surface(screen.get_size())
    background = background.convert()
    background.fill((0, 0, 0))
    
    # Display The Background
    screen.blit(background, (0, 0))
    #clock = pg.time.Clock()
    
    #prepare objects
    vorGame = target(targetSize,mac,vorTrain,vRange,hRange)

    
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
        vorGame.draw()
    pg.quit()
    vorGame.safeIMUDisconnect()
    print("Excercise finished. Bye !")


#for testing purposes
if __name__ == "__main__":
    vor()