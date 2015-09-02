from threading import Thread
import mido

class MockMidi():
    def __init__(self, player, rnn):
        self.player = player
        self.rnn = rnn
        mido.set_backend('mido.backends.rtmidi')
        self.midiModeNames = ["continuous", "discrete"]
        self.setMidiMode(0)
        self.resetPads()
        self.thread = Thread( target = self.listenToMidi )
        self.thread.start()
        self.currentValues = {}
    
    def resetPads(self):
        pass
    
    def setDisplayLine(self, line, string):
        pass
    
    def clearDisplayLine(self, line):
        pass
    
    def setMidiMode(self, index):
        self.midiMode = index
    
    def toggleNetListening(self):
        isOn = self.rnn.toggleListening()
    
    def toggleNetPlaying(self):
        isOn = self.rnn.togglePlaying()
    
    def setParameterFromMidi(self, parameter, value):
        previousValue = self.currentValues[parameter] if parameter in self.currentValues else 0
        self.setParameter(parameter, value)
        delta = value-previousValue
        if delta is not 0:
            self.rnn.setValueChange(parameter, delta)
    
    def changeParameterFromNet(self, parameter, valueChange): #relative parameter
        previousValue = self.currentValues[parameter] if parameter in self.currentValues else 0
        newValue = min(max(previousValue+valueChange,0), 127)
        #print "change", parameter, valueChange, newValue
        self.setParameter(parameter, newValue)
    
    def setParameter(self, parameter, value):
        self.currentValues[parameter] = value
        if 36 <= parameter and parameter <= 99: #note played
            if self.midiMode is 0:
                self.player.playOrModifyGranularObject(parameter-36, value)
            elif self.midiMode is 1:
                self.player.playSound(parameter-36, value)
            #IF MODE PATTERN #self.player.switchToPattern(msg.note)
    
    def listenToMidi(self):
        self.isRunning = True
        try:
            #print mido.get_input_names()
            self.inport = mido.open_input('MidiMock OUT')
            while self.isRunning:
                msg = self.inport.receive()
                #print msg
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
                if msg.type is 'polytouch':
                    self.setParameterFromMidi(msg.note, msg.value)
                if self.midiMode is 1 and msg.type is 'note_on' or msg.type is 'note_off':
                    self.setParameterFromMidi(msg.note, msg.velocity)
        except IOError as e:
            print e
    
    def stop(self):
        self.isRunning = False
        self.thread.join()




class PushMidi():
    
    def __init__(self, player, rnn):
        self.player = player
        self.rnn = rnn
        mido.set_backend('mido.backends.rtmidi')
        self.outport = mido.open_output('Ableton Push User Port')
        self.midiModeNames = ["continuous", "discrete"]
        self.setMidiMode(0)
        self.resetPads()
        self.thread = Thread( target = self.listenToMidi )
        self.thread.start()
        self.currentValues = {}
    
    def resetPads(self):
        for i in range(36,100):
            self.setPadLight(i, 0)
    
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
    
    def toggleNetListening(self):
        isOn = self.rnn.toggleListening()
        self.setButtonLight(86, isOn)
    
    def toggleNetPlaying(self):
        isOn = self.rnn.togglePlaying()
        self.setButtonLight(85, isOn)
    
    def setParameterFromMidi(self, parameter, value):
        previousValue = self.currentValues[parameter] if parameter in self.currentValues else 0
        self.setParameter(parameter, value)
        delta = value-previousValue
        if delta is not 0:
            self.rnn.setValueChange(parameter, delta)
    
    def changeParameterFromNet(self, parameter, valueChange): #relative parameter
        previousValue = self.currentValues[parameter] if parameter in self.currentValues else 0
        newValue = min(max(previousValue+valueChange,0), 127)
        #print "change", parameter, valueChange, newValue
        self.setParameter(parameter, newValue)
    
    def setParameter(self, parameter, value):
        self.currentValues[parameter] = value
        if 36 <= parameter and parameter <= 99: #note played
            if self.midiMode is 0:
                self.player.playOrModifyGranularObject(parameter-36, value)
            elif self.midiMode is 1:
                self.player.playSound(parameter-36, value)
            self.setPadLight(parameter, value)
            #IF MODE PATTERN #self.player.switchToPattern(msg.note)
    
    def setPadLight(self, note, velocity):
        velocity = int(round(4.0*velocity/128))
        self.outport.send(mido.Message('note_on', note=note, velocity=velocity))
    
    def setButtonLight(self, index, turnOn):
        if turnOn:
            self.outport.send(mido.Message('control_change', control=index, value=4))
        else:
            self.outport.send(mido.Message('control_change', control=index, value=0))
    
    def listenToMidi(self):
        self.isRunning = True
        try:
            #print mido.get_input_names()
            self.inport = mido.open_input('Ableton Push User Port')
            while self.isRunning:
                msg = self.inport.receive()
                #print msg
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
                if msg.type is 'polytouch':
                    self.setParameterFromMidi(msg.note, msg.value)
                if self.midiMode is 1 and msg.type is 'note_on' or msg.type is 'note_off':
                    self.setParameterFromMidi(msg.note, msg.velocity)
        except IOError as e:
            print e
    
    def stop(self):
        self.isRunning = False
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