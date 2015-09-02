import os, sys, inspect, thread, time, numpy
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

from pushmidi import PushMidi
from livernns import LiveDoubleRNN

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
    
    def __init__(self, space):
        self.space = space
        address = '192.168.1.128', 57120
        self.server = OSC.OSCServer(address)
        #self.server.addMsgHandler("default", self.handleDefault)
        self.server.addMsgHandler("/create", self.handleCreate)
        self.server.addMsgHandler("/kill", self.handleKill), 
        self.thread = Thread( target = self.server.serve_forever )
        self.thread.start()
    
    def handleCreate(self, addr, tags, stuff, source):
        self.space.addObject(stuff[0])
        address = "/sphere" + str(stuff[0]) + "/position"
        self.server.addMsgHandler(address, self.handleUpdate)
    
    def handleUpdate(self, addr, tags, stuff, source):
        index = int(addr[7:-9])
        self.space.updateObject(index, stuff[0], stuff[1], stuff[2], stuff[3])
    
    def handleKill(self, addr, tags, stuff, source):
        self.space.removeObject(stuff[0])
        #self.server.removeMsgHandler("/sphere" + stuff[0] + "/position")
    
    def stop(self):
        self.server.close()
        self.thread.join()

class Audio():
    
    def __init__(self):
        self.server = Server(buffersize=256).boot()
        self.server.start()
    
    def stop(self):
        self.server.stop()
        
        print "server stopped"

class SoundObject():
    
    def __init__(self, filename, amplitude=1, start=None, end=None, durationRatio=1, disto=None, reverb=None, pan=None):
        if start is None:
            self.snd = SndTable(filename)
        else:
            duration = durationRatio*(end-start)
            self.snd = SndTable(filename, start=start, stop=start+duration)
        if pan is None:
            pan = random.uniform(0,1)
        if reverb is None:
            reverb = random.uniform(0.3,1)
        if disto is None:
            disto = random.uniform(0,1)
        self.pan = pan
        self.disto = 0
        self.reverb = reverb
        self.amplitude = amplitude
    
    def play(self):
        signal = self.getSignal() #IMPLEMENT IN INHERITING CLASSES
        signal = Pan(signal, outs=2, pan=self.pan).out()
        return Disto(signal, drive=self.disto, slope=.8, mul=.15).out()
        #self.out = signal
    
    def stopAndClean(self):
        Thread( target = self.stopOut ).start()
    
    def stopOut(self):
        time.sleep(1)
        if hasattr(self, 'out'):
            self.out.stop()
            del self.out

class GranularSoundObject(SoundObject):
    
    def __init__(self, filename, amplitude=1, start=None, end=None, durationRatio=1, disto=None, reverb=None, pan=None):
        SoundObject.__init__(self, filename, amplitude, start, end, durationRatio, 0, 0.2, pan)
        self.position = 0
    
    def getSignal(self):
        self.granulator = Granulator(self.snd, HannTable(), [1, 1.001], grains=randint(10,20), dur=Noise(.001, .1), basedur=0.1, mul=self.amplitude)
        return self.granulator.out()
    
    def update(self, position, amplitude, duration=None, pitch=None):
        self.position = position
        self.granulator.setPos(position*self.snd.getSize()[0])
        self.granulator.setMul(amplitude)
        if duration != None:
            self.granulator.setDur(duration*0.3)
        if pitch != None:
            self.granulator.setPitch(pitch)
    
    def getPosition(self):
        return self.position

class SampleSoundObject(SoundObject):
    
    def __init__(self, filename, amplitude=1, frequencyRatio=1, start=None, end=None, durationRatio=1, disto=None, reverb=None, pan=None):
        SoundObject.__init__(self, filename, amplitude, start, end, durationRatio, disto, reverb, pan)
        if self.snd.getDur() > 0:
            self.frequency = frequencyRatio*(1/self.snd.getDur())
        else:
            self.frequency = 1
        
    def getSignal(self):
        return TableRead(table=self.snd, freq=self.frequency, mul=self.amplitude).out()

class ObjectSpace():
    
    def __init__(self, filename, durations):
        self.filename = filename
        self.durations = durations
        self.objects = {}
    
    def addObject(self, index):
        randomIndex = randint(0,len(self.durations)-2)
        start = self.durations[randomIndex]
        end = self.durations[randomIndex+1]
        self.objects[index] = GranularSoundObject(self.filename, 0.3, start, end, 0)
        self.objects[index].play()
    
    def updateObject(self, index, position, amplitude, duration, pitch):
        self.objects[index].update(position, amplitude, duration, pitch)
    
    def removeObject(self, index):
        self.objects[index].stopAndClean()

class Loop():
    
    def __init__(self, objects, duration, division, onsets):
        finegrainedness = 100
        self.objects = objects
        beatDuration = float(duration)/division/finegrainedness
        onsets = self.getOnsets(onsets, division)
        onsets = (finegrainedness*numpy.array(onsets)).tolist()
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
        for x in self.oldObjects:
            x.stopAndClean()
    
    def playNextObject(self):
        self.objects[self.index].play()
        self.index = (self.index+1) % len(self.objects)
    
    def play(self):
        self.seq.play() #seq=[2,1,3,1,1,1,2,1], poly=1).play()
        self.trig = TrigFunc(self.seq, self.playNextObject)
    
    def stop(self):
        self.seq.stop()
        for x in self.objects:
            x.stopAndClean()

class RhythmPattern():
    
    def __init__(self, durations):
        self.durations = durations
        self.loopCount = 5#randint(1,20)
        self.durationRatio = 1
        self.frequencyRatio = 1
        self.filenames = ["miroglio/808 Bass A-1.wav", "miroglio/garden3.wav"]
        self.loops = []
        tempoFactor = ((randint(1,5)-3)/10)+1 #0.8,0.9,1,1.1,1.2
        duration = randint(2,4)
        division = 8*duration
        self.loops.append(Loop(self.createSimpleObject(self.filenames[0]), duration, division, duration))
        for x in range(0, self.loopCount):
            onsets = randint(1,2*duration)
            self.loops.append(Loop(self.createNewObjects(self.filenames[1], onsets), duration, division, onsets))
    
    def createNewObjects(self, filename, objectsInSequence):
        objects = []
        for x in range(0, objectsInSequence):
            randomIndex = randint(0,len(self.durations)-2)
            start = self.durations[randomIndex]
            end = self.durations[randomIndex+1]
            objects.append(SampleSoundObject(filename, 0.6, self.frequencyRatio, start, end, randint(1,4))) #random.uniform(0,1)))
        return objects
    
    def createSimpleObject(self, filename):
        return [SampleSoundObject(filename, 1, random.uniform(0.6,1), pan=0.5, disto=0, reverb=0)]
    
    def replaceObjects(self):
        for x in range(0, len(self.loops)):
            f = min(x, 1)
            self.loops[x].setObjects(self.createNewObjects(self.filenames[f], self.loops[x].getObjectCount()))
    
    def setImprecision(self):
        for x in self.loops:
            currentOnsets = x.getOnsets()
            currentOnsets = [ x+randint(-5,5) for x in currentOnsets ]
    
    def play(self):
        for loop in self.loops:
            loop.play()
    
    def stop(self):
        for loop in self.loops:
            loop.stop()

class Player():
    
    def __init__(self):
        self.audio = Audio()
        self.durations = RdfReader().loadDurations("miroglio/garden3_onset.n3", "n3")
        self.durationRatio = 1
        self.frequencyRatio = 1
        self.patterns = {}
        self.currentPattern = None
        self.objects = {}
        self.granularObjects = {}
        self.mix = Mixer(outs=2, chnls=2, time=.025)
        #self.out = self.mix[0]
        self.reverbSend = Freeverb(self.mix[1], size=.8, damp=.2, bal=1, mul=1).out()
        #self.reverbSend = Freeverb(signal, size=self.reverb, bal=self.reverb).out()
    
    def playSound(self, index, velocity):
        amp = 0.99*velocity/127
        start = self.durations[index]
        end = self.durations[index+1]
        newObject = SampleSoundObject("miroglio/garden3.wav", amp, self.frequencyRatio, start, end, reverb=1)
        if index in self.objects:
            self.objects[index].stopAndClean()
            self.mix.delInput(index)
            print "streams", self.audio.server.getNumberOfStreams()
        self.mix.addInput(index, newObject.play())
        self.mix.setAmp(index, 1, newObject.reverb*10)
        self.objects[index] = newObject
    
    def playOrModifyGranularObject(self, index, amp):
        amp = 0.99*amp/127
        if index not in self.granularObjects:
            start = self.durations[index]
            end = self.durations[index+1]
            self.granularObjects[index] = GranularSoundObject("miroglio/garden3.wav", amp, start, end)
            self.granularObjects[index].play()
            self.mix.addInput(index, self.granularObjects[index].play())
            self.mix.setAmp(index, 0, 0)
            self.mix.setAmp(index, 1, self.granularObjects[index].reverb*10)
        else:
            position = (self.granularObjects[index].getPosition()+0.002) % 1
            self.granularObjects[index].update(position, amp)
            if amp == 0:
                self.granularObjects[index].stopAndClean()
                #del self.objects[index]
                print "streams", self.audio.server.getNumberOfStreams()
    
    def switchToPattern(self, index):
        #play new pattern or replace sounds
        if index == self.currentPattern:
            self.patterns[self.currentPattern].replaceObjects()
        if index not in self.patterns:
            self.patterns[index] = RhythmPattern(self.durations)
        self.patterns[index].play()
        #stop old pattern
        if self.currentPattern != None:
            self.patterns[self.currentPattern].stop()
        self.currentPattern = index
    
    def getCurrentPattern(self):
        return self.patterns[self.currentPattern]
    
    def stop(self):
        for loop in self.loops:
            loop.stop()
        self.audio.stop()



def main():
    
    player = Player()
    rnn = LiveDoubleRNN()
    pushMidi = PushMidi(player, rnn)
    rnn.setPushMidi(pushMidi)
    
    durations = RdfReader().loadDurations("miroglio/garden3.n3", "n3")
    space = ObjectSpace("miroglio/garden3.wav", durations)
    #oscListener = OscListener(space)
    
    """randomIndex = randint(0,len(durations)-2)
    start = durations[randomIndex]
    end = durations[randomIndex+1]
    g = GranularSoundObject("miroglio/garden3.wav", 0.3, start, end, 1)
    g.play()"""
    
    
    # Create a listener and controller
    #listener = LeapListener(player)
    #controller = Leap.Controller()

    # Have the sample listener receive events from the controller
    #controller.add_listener(listener)
    
    #oscListener = OscListener(player)
    
    #player.audio.server.gui(locals(), exit=True)
    
    #midiListener.stop()
    
    """s.stop()
    time.sleep(1)
    exit()"""
    
    try:
        while True:
            pass
    except KeyboardInterrupt:
        pushMidi.stop()
        rnn.stop()
        player.audio.server.stop()
        time.sleep(1)
        player.audio.server.shutdown()
        exit()

if __name__ == "__main__":
    main()