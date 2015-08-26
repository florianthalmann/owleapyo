import time
from owleapyo import *
import rdflib

def createSoundObject(pan=0.5):
    return SampleSoundObject("miroglio/808 Bass A.wav", 1, random.uniform(0,1), reverb=0)

def testPan(audio):
    so = createSoundObject(0)
    so.play()
    time.sleep(2)
    so.stopAndClean()
    so2 = createSoundObject(1)
    so2.play()
    time.sleep(2)
    so2.stopAndClean()

def testSoundObject(audio):
    print "---test sound object"
    for x in range(2):
        print audio.server.getNumberOfStreams()
        so = createSoundObject()
        so.play()
        print audio.server.getNumberOfStreams()
        time.sleep(1)
        so.stopAndClean()
        time.sleep(1)
    print audio.server.getNumberOfStreams()

def testLoop(audio):
    print "---test loop"
    print audio.server.getNumberOfStreams()
    l = Loop([createSoundObject(),createSoundObject(),createSoundObject()], 1, 64, 12)
    l.play()
    time.sleep(1)
    print audio.server.getNumberOfStreams()
    l.stop()
    time.sleep(1)
    print audio.server.getNumberOfStreams()

def testRhythmPattern(audio):
    print "---test rhythm pattern"
    print audio.server.getNumberOfStreams()
    durations = RdfReader().loadDurations("miroglio/garden3.n3", "n3")
    r = RhythmPattern(durations)
    r.play()
    time.sleep(1)
    print audio.server.getNumberOfStreams()
    r.replaceObjects()
    time.sleep(1)
    print audio.server.getNumberOfStreams()
    r.stop()
    time.sleep(1)
    print audio.server.getNumberOfStreams()

def main():
    audio = Audio()
    
    #testSoundObject(audio)
    #testLoop(audio)
    #testRhythmPattern(audio)
    testPan(audio)
    
    print audio.server.getNumberOfStreams()
    
    #audio.server.stop()
    #time.sleep(.5)
    #audio.server.shutdown()
    #time.sleep(.5)
    #del audio

if __name__ == "__main__":
    main()