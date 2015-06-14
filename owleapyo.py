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

class Audio():
    
    def __init__(self):
        self.server = Server().boot()
        self.server.start()
    
    def stop(self):
        self.server.stop()

class SoundObject():
    
    def __init__(self, filename, start, end, durationRatio, frequencyRatio):
        duration = durationRatio*(end-start)
        frequency = frequencyRatio*(1/duration)
        stop = start+duration
        snd = SndTable("king.wav", start=start, stop=stop)
        self.out = TableRead(table=snd, freq=frequency).out()

class Player(Thread):
    
    def __init__(self):
        super(Player, self).__init__()
        self._stop = threading.Event()
        self.audio = Audio()
        self.durations = RdfReader().loadDurations("king.n3", "n3")
        self.waitTime = .3
        self.durationRatio = 1;
        self.frequencyRatio = 1;
    
    def playNewObject(self):
        randomIndex = randint(0,len(self.durations)-2)
        start = self.durations[randomIndex]
        end = self.durations[randomIndex+1]
        self.a = SoundObject("king.wav", start, end, self.durationRatio, self.frequencyRatio).out
    
    def run(self):
        while (not self._stop.is_set()):
            print self.waitTime, self.durationRatio, self.frequencyRatio
            self.playNewObject()
            self._stop.wait(self.waitTime)
            pass
    
    def stop(self):
        self._stop.set()
        self.audio.stop()

def main():
    
    player = Player()
    
    # Create a listener and controller
    listener = LeapListener(player)
    controller = Leap.Controller()

    # Have the sample listener receive events from the controller
    controller.add_listener(listener)
    
    player.start()
    
    # Keep this process running until Enter is pressed
    print "Press Enter to quit..."
    try:
        sys.stdin.readline()
        player.stop()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()