import time
from owleapyo import *
import rdflib

def createSoundObject(pan=0.5):
    return SampleSoundObject("miroglio/808 Bass A-1.wav", 1, 1, pan=pan, reverb=0)

def testPan(audio):
    so = createSoundObject(-1)
    so.play()
    time.sleep(1)
    so.stopAndClean()
    so2 = createSoundObject(2)
    so2.play()
    time.sleep(1)
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
    durations = RdfReader().loadDurations("miroglio/garden3_onset.n3", "n3")
    for i in range(10):
        r = RhythmPattern(durations)
        r.play(0, 1)
        time.sleep(0.1)
        print audio.server.getNumberOfStreams()
        r.replaceObjects()
        time.sleep(0.1)
        print audio.server.getNumberOfStreams()
        r.stopAndClean()
    time.sleep(5)
    print [x.getStreamObject() for x in audio.server.getStreams()]

def testPlayer():
    player = Player(PushMidi())
    time.sleep(1)
    print player.audio.server.getNumberOfStreams()
    player.playOrModifyGranularObject(0,127)
    time.sleep(1)
    print player.audio.server.getNumberOfStreams()
    player.playOrModifyGranularObject(0,127)
    time.sleep(1)
    print player.audio.server.getNumberOfStreams()
    player.playOrModifyGranularObject(1,127)
    time.sleep(1)
    print player.audio.server.getNumberOfStreams()
    player.playOrModifyGranularObject(2,127)
    time.sleep(1)
    print player.audio.server.getNumberOfStreams()
    player.playOrModifyGranularObject(3,127)
    time.sleep(1)
    print player.audio.server.getNumberOfStreams()
    player.deleteAllObjects()
    time.sleep(3)
    print player.audio.server.getNumberOfStreams()

def test():
    f = Fader(fadein=0.5, fadeout=0.5, dur=2, mul=.5)
    a = BrownNoise(mul=f).mix(2).out()
    def repeat():
        f.play()
    pat = Pattern(function=repeat, time=2).play()

def main():
    audio = Audio()
    
    testPan(audio)
    #testSoundObject(audio)
    #testLoop(audio)
    #test()
    #testRhythmPattern(audio)
    #testPlayer()
    
    #print audio.server.getNumberOfStreams()
    
    #audio.server.stop()
    #time.sleep(.5)
    #audio.server.shutdown()
    #time.sleep(.5)
    #del audio

if __name__ == "__main__":
    main()