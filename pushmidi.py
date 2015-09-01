from threading import Thread
import mido

class PushMidi():
    
    def __init__(self, player):
        self.player = player
        mido.set_backend('mido.backends.rtmidi')
        self.outport = mido.open_output('Ableton Push User Port')
        #self.setDisplayLine(2, "Yeah, let's play some fucking great sound")
        #self.clearDisplayLine(2)
        self.midiModeNames = ["continuous", "discrete"]
        self.setMidiMode(0)
        self.thread = Thread( target = self.listenToMidi )
        self.thread.start()
    
    def initUserMode(self):
        print mido.get_output_names()
        
        self.outport.send(mido.Message('note_on', note=43, velocity=3))
        #240,71,127,21,<24+line(0-3)>,0,69,0,<68xChars>,247
        #240,71,127,21,98,0,1,1,247
    
    def setDisplayLine(self, line, string):
        numbers = [ord(c) for c in string]
        
        #pad string with numbers
        back = True
        while len(numbers) < 68:
            if back == True:
                numbers.append(32)
            else:
                numbers.insert(0, 32)
            back = not back
        
        #prepare and send message
        data = [71,127,21,24+line,0,69,0]
        data.extend(numbers)
        self.outport.send(mido.Message('sysex', data=data))
    
    def clearDisplayLine(self, line):
        self.outport.send(mido.Message('sysex', data=[71,127,21,28+line,0,0]))
    
    def setMidiMode(self, index):
        self.midiMode = index
        self.setDisplayLine(3, self.midiModeNames[self.midiMode])
    
    def toggleNetListening(self, index):
        isOn = self.player.toggleNetListening()
        self.setButtonLight(self, 86, isOn)
    
    def toggleNetPlaying(self, index):
        isOn = self.player.toggleNetPlaying()
        self.setButtonLight(self, 85, isOn)
    
    def setButtonLight(self, index, turnOn):
        if turnOn:
            self.outport.send(mido.Message('note_on', note=index, velocity=4))
        else:
            self.outport.send(mido.Message('note_on', note=index, velocity=0))
    
    def listenToMidi(self):
        self.isRunning = True
        try:
            #print mido.get_input_names()
            self.inport = mido.open_input('Ableton Push User Port')
            while self.isRunning:
                msg = self.inport.receive()
                print msg
                if msg.type == 'control_change':
                    if msg.control is 20 and msg.value is 127:
                        self.setMidiMode(0)
                    if msg.control is 21 and msg.value is 127:
                        self.setMidiMode(1)
                    if msg.control is 86 and msg.value is 127:
                        self.toggleNetListening()
                    if msg.control is 85 and msg.value is 127:
                        self.toggleNetPlaying()
                    #self.player.getCurrentPattern().setImprecision(msg.value)
                    pass
                if self.midiMode is 0:
                    if msg.type == 'polytouch':
                        self.player.playOrModifyGranularObject(msg.note-36, msg.value)
                    if msg.type == 'note_off':
                        self.player.playOrModifyGranularObject(msg.note-36, 0)
                else:
                    if msg.type == 'note_on':
                        self.player.playSound(msg.note-36, msg.velocity)
                        #self.player.switchToPattern(msg.note)
        except IOError as e:
            print e
    
    def stop(self):
        self.isRunning = False
        if hasattr(self, 'thread') and self.thread.isAlive():
            self.thread.join()


def main():
    
    midi = PushMidi()
    
    try:
        while True:
            pass
    except KeyboardInterrupt:
        midi.stop()
        exit()

if __name__ == "__main__":
    main()