import os, sys, inspect, thread, time
from threading import Thread
from random import randint

src_dir = os.path.dirname(inspect.getfile(inspect.currentframe()))
arch_dir = '../lib/x64' if sys.maxsize > 2**32 else '../lib/x86'
sys.path.insert(0, os.path.abspath(os.path.join(src_dir, arch_dir)))
sys.path += ["/Developer/LeapSDK/lib/"]

import Leap
from Leap import CircleGesture, KeyTapGesture, ScreenTapGesture, SwipeGesture
from pyo import *
import rdflib
from rdflib import XSD
import OSC
import mido

class RdfReader():
    
    def parseXSDDuration(self, duration):
        return float(duration[2:-1])
    
    def loadDurations(self, filename, format):
        g = rdflib.Graph()
        g.load(filename, format=format)
        result = g.query(
            """SELECT DISTINCT ?dur
               WHERE {
                  ?a tl:at ?dur .
               }""")
        durations = []
        for row in result:
            durations.append(self.parseXSDDuration(row[0]))
        durations.sort()
        return durations

class LeapListener(Leap.Listener):
    
    def __init__(self, player):
        self.player = player
        super(LeapListener, self).__init__()

    def on_connect(self, controller):
        print "Connected"

    def on_frame(self, controller):
        frame = controller.frame()
        position = frame.hands.rightmost.palm_position
        if position.x != 0:
            self.player.waitTime = (position.y) / 1000
            self.player.durationRatio = (position.x +300) / 500
            self.player.frequencyRatio = (-position.z +300) / 300

class OscListener():
    
    def __init__(self, player):
        self.player = player
        address = '192.168.0.7', 57120
        self.server = OSC.OSCServer(address)
        self.server.addMsgHandler("/sphere0/position", self.handleMessage)
        self.thread = threading.Thread( target = self.server.serve_forever )
        self.thread.start()
    
    def handleMessage(self, addr, tags, stuff, source):
        #print addr, tags, stuff, source
        if addr == "/sphere0/position":
            self.player.waitTime = stuff[0]
    
    def stop(self):
        self.server.close()
        self.thread.join()

class Audio():
    
    def __init__(self):
        self.server = Server().boot()
        self.server.start()
    
    def stop(self):
        self.server.stop()

class SoundObject():
    
    def __init__(self, filename, start, end, durationRatio, frequencyRatio):
        duration = durationRatio*(end-start)
        self.frequency = frequencyRatio*(1/duration)
        stop = start+duration
        self.snd = SndTable("king.wav", start=start, stop=stop)
        self.pan = random.uniform(0,1)
        self.reverb = random.uniform(0,1)
        
    def play(self):
        table = TableRead(table=self.snd, freq=self.frequency).out()
        table = Freeverb(table, size=self.reverb, bal=self.reverb).out()
        self.out = Pan(table, outs=2, pan=self.pan).out()

class Loop():
    
    def __init__(self, objects, duration, division, onsets):
        self.objects = objects
        beatDuration = float(duration)/division
        onsets = self.getOnsets(onsets, division)
        self.seq = Seq(time=beatDuration, seq=onsets, poly=1)
        print onsets
        self.index = 0
    
    def getOnsets(self, onsetCount, total):
        dividers = sorted(random.sample(xrange(1, total), onsetCount - 1))
        return [a - b for a, b in zip(dividers + [total], [0] + dividers)]
    
    def getObjectCount(self):
        return len(self.objects)
    
    def setObjects(self, objects):
        self.oldObjects = self.objects #temp save last objects to not stop them immediately
        self.objects = objects
    
    def playNextObject(self):
        self.objects[self.index].play()
        self.index = (self.index+1) % len(self.objects)
    
    def play(self):
        self.seq.play() #seq=[2,1,3,1,1,1,2,1], poly=1).play()
        self.trig = TrigFunc(self.seq, self.playNextObject)
    
    def stop(self):
        self.seq.stop()

class Player():
    
    def __init__(self):
        self.audio = Audio()
        self.durations = RdfReader().loadDurations("king.n3", "n3")
        self.durationRatio = 1
        self.frequencyRatio = 1
        self.loops = []
    
    def createNewObjects(self, objectsInSequence):
        objects = []
        for x in range(0, objectsInSequence):
            randomIndex = randint(0,len(self.durations)-2)
            start = self.durations[randomIndex]
            end = self.durations[randomIndex+1]
            objects.append(SoundObject("king.n3", start, end, self.durationRatio, self.frequencyRatio))
        return objects
    
    def replaceObjectsInLoop(self):
        for loop in self.loops:
            loop.setObjects(self.createNewObjects(loop.getObjectCount()))
    
    def start(self):
        self.loops.append(Loop(self.createNewObjects(1), 3, 16, 4))
        self.loops.append(Loop(self.createNewObjects(2), 3, 16, 9))
        self.loops.append(Loop(self.createNewObjects(1), 3, 16, 2))
        self.loops.append(Loop(self.createNewObjects(5), 3, 16, 5))
        for loop in self.loops:
            loop.play()
    
    def stop(self):
        for loop in self.loops:
            loop.stop()
        self.audio.stop()

def main():
    
    player = Player()
    
    # Create a listener and controller
    #listener = LeapListener(player)
    #controller = Leap.Controller()

    # Have the sample listener receive events from the controller
    #controller.add_listener(listener)
    
    #oscListener = OscListener(player)
    
    player.start()
    
    inport = mido.open_input()
    
    while True:
        msg = inport.receive()
        if msg.type == 'note_on':
            print msg
            player.replaceObjectsInLoop()
    
    """while True:
        x = raw_input('Press Enter for new sounds...')
        if x == 'done':
            break
        player.replaceObjectsInLoop()"""

if __name__ == "__main__":
    main()