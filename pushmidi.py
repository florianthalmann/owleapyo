from threading import Thread
import math
import mido

class MidiController():
    
    def __init__(self):
        mido.set_backend('mido.backends.rtmidi')
        try:
            self.outport = mido.open_output('Ableton Push User Port')
        except AttributeError:
            pass
        self.statusLine = {}
        self.modeNames = ["grain mode", "sample mode", "loop mode"]
        self.setNetMode(0)
        self.setMidiMode(0)
        self.thread = Thread( target = self.listenToMidi )
        self.thread.start()
        self.currentValues = {}
    
    def setNetAndPlayer(self, rnn, player):
        self.rnn = rnn
        self.player = player
    
    def setMidiMode(self, index):
        self.midiMode = index
        self.setStatusLine(1, "midi: " + self.modeNames[self.midiMode])
        self.setButtonLight(20, index is 0)
        self.setButtonLight(21, index is 1)
        self.setButtonLight(22, index is 2)
    
    def setNetMode(self, index):
        self.netMode = index
        self.setStatusLine(2, "net: " + self.modeNames[self.netMode])
        self.setButtonLight(102, index is 0)
        self.setButtonLight(103, index is 1)
        self.setButtonLight(104, index is 2)
    
    def toggleNetListening(self):
        isOn = self.rnn.toggleListening()
        self.setButtonLight(86, isOn)
    
    def toggleNetPlaying(self):
        isOn = self.rnn.togglePlaying()
        self.setButtonLight(85, isOn)
    
    def setParameterFromMidi(self, parameter, value):
        previousValue = self.currentValues[parameter] if parameter in self.currentValues else 0
        self.setParameter(parameter, value, self.midiMode)
        delta = value-previousValue
        if delta is not 0:
            self.rnn.setValueChange(parameter, delta)
    
    def changeParameterFromNet(self, parameter, valueChange): #relative parameter
        previousValue = self.currentValues[parameter] if parameter in self.currentValues else 0
        newValue = min(max(previousValue+valueChange,0), 127)
        #print "change", parameter, valueChange, newValue
        self.setParameter(parameter, newValue, self.netMode)
    
    def setParameter(self, parameter, value, mode):
        self.currentValues[parameter] = value
        if 36 <= parameter and parameter <= 99: #note played
            if mode is 0:
                self.player.playOrModifyGranularObject(parameter-36, value)
            elif mode is 1:
                self.player.playSound(parameter-36, value)
            elif mode is 2 and value > 0:
                self.player.addSoundToLoop(parameter-36, value)
            self.setPadLight(parameter, value)
            #IF MODE PATTERN #self.player.switchToPattern(msg.note)
    
    def setStatusLine(self, index, string):
        self.statusLine[index] = string
        status = ""
        for i in self.statusLine:
            status += str(self.statusLine[i]) + " | "
        self.setDisplayLine(3, status)
    
    def setDisplayLine(self, line, string):
        print line, string
    
    def clearDisplayLine(self, line):
        pass
    
    def setButtonLight(self, index, turnOn):
        pass
    
    def setPadLight(self, note, velocity):
        pass
    
    def listenToMidi(self):
        self.isRunning = True
        try:
            #print mido.get_input_names()
            self.inport = mido.open_input(self.getInputPortName())
            while self.isRunning:
                msg = self.inport.receive()
                #print msg
                if msg.type == 'control_change':
                    if msg.control is self.getSegmentControl():
                        self.updateSegmentsIndex(msg.value)
                    if msg.control is 20 and msg.value is 127:
                        self.setMidiMode(0)
                    if msg.control is 21 and msg.value is 127:
                        self.setMidiMode(1)
                    if msg.control is 22 and msg.value is 127:
                        self.setMidiMode(2)
                    if msg.control is 102 and msg.value is 127:
                        self.setNetMode(0)
                    if msg.control is 103 and msg.value is 127:
                        self.setNetMode(1)
                    if msg.control is 104 and msg.value is 127:
                        self.setNetMode(2)
                    if msg.control is 86 and msg.value is 127:
                        self.toggleNetListening()
                    if msg.control is 85 and msg.value is 127:
                        self.toggleNetPlaying()
                    if msg.control is 87 and msg.value is 127:
                        self.rnn.resetTrainingData()
                    if msg.control is 14:
                        self.switchLoop(msg.value)
                    #self.player.getCurrentPattern().setImprecision(msg.value)
                    pass
                if self.midiMode is 0 and msg.type is 'polytouch':
                    self.setParameterFromMidi(msg.note, msg.value)
                elif self.midiMode is 1 and (msg.type is 'note_on' or msg.type is 'note_off'):
                    self.setParameterFromMidi(msg.note, msg.velocity)
                elif self.midiMode is 2 and (msg.type is 'note_on' or msg.type is 'note_off'):
                    self.setParameterFromMidi(msg.note, msg.velocity)
        except IOError as e:
            print e
    
    def stop(self):
        self.isRunning = False
        self.thread.join()


class MockMidi(MidiController):
    
    def getInputPortName(self):
        return 'MidiMock OUT'
    
    def getSegmentControl(self):
        return 1
    
    def updateSegmentsIndex(self, value):
        self.player.setSegmentsIndex(64*value)


class PushMidi(MidiController):
    
    def __init__(self):
        MidiController.__init__(self)
        self.reset()
    
    def getInputPortName(self):
        return 'Ableton Push User Port'
    
    def getOutputPortName(self):
        return 'Ableton Push User Port'
    
    def getSegmentControl(self):
        return 15
    
    def updateSegmentsIndex(self, value):
        if value > 64:
            value -= 128
        self.player.changeSegmentsIndex(64*value)
    
    def switchLoop(self, value):
        if value > 64:
            value -= 128
        self.player.switchLoop(value)
    
    def reset(self):
        for i in range(36,100):
            self.setPadLight(i, 0)
        for i in range(3):
            self.clearDisplayLine(i)
        self.setButtonLight(85, 0)
        self.setButtonLight(86, 0)
        self.setButtonLight(87, 1)
    
    def setDisplayLine(self, line, string):
        ascii = [ord(c) for c in string]
        
        #pad ascii array with spaces
        back = True
        while len(ascii) < 68:
            if back == True:
                ascii.append(32)
            else:
                ascii.insert(0, 32)
            back = not back
        
        #prepare and send message
        data = [71,127,21,24+line,0,69,0]
        data.extend(ascii)
        self.outport.send(mido.Message('sysex', data=data))
    
    def clearDisplayLine(self, line):
        self.outport.send(mido.Message('sysex', data=[71,127,21,28+line,0,0]))
    
    def setPadLight(self, note, velocity):
        if velocity > 0:
            velocity = int(math.floor(5.0*velocity/128))+1
        self.outport.send(mido.Message('note_on', note=note, velocity=velocity))
    
    def setButtonLight(self, index, turnOn):
        if turnOn:
            self.outport.send(mido.Message('control_change', control=index, value=4))
        else:
            self.outport.send(mido.Message('control_change', control=index, value=0))


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