"""
Minimal character-level Vanilla RNN model. Written by Andrej Karpathy (@karpathy)
BSD License
"""
from threading import Thread
import time, math
import numpy as np
import mido

class LiveByteRNN():
    
    def __init__(self):
        # data I/O
        self.vocab_size = 128

        # hyperparameters
        self.hidden_size = 300 # size of hidden layer of neurons
        self.learning_rate = 0.1

        # model parameters
        self.Wxh = np.random.randn(self.hidden_size, self.vocab_size)*0.01 # input to hidden
        self.Whh = np.random.randn(self.hidden_size, self.hidden_size)*0.01 # hidden to hidden
        self.Why = np.random.randn(self.vocab_size, self.hidden_size)*0.01 # hidden to output
        self.bh = np.zeros((self.hidden_size, 1)) # hidden bias
        self.by = np.zeros((self.vocab_size, 1)) # output bias
        
        self.n = 0
        self.mWxh, self.mWhh, self.mWhy = np.zeros_like(self.Wxh), np.zeros_like(self.Whh), np.zeros_like(self.Why)
        self.mbh, self.mby = np.zeros_like(self.bh), np.zeros_like(self.by) # memory variables for Adagrad
        
        """for i in range(100):
            print self.learnAndSample([0,0,0,0,0,0,1,0,0,0,1,0,0,0,0,0,2,0,0,0,0,0,0,0])
        
        for i in range(100):
            print self.learnAndSample([33,33,33,33,33,0,0,0,0,0,0,33,33,33,33,33,33,33,33,0,0,0,0,0])"""
    
    def learnAndSample(self, input):
        if self.n == 0:
            self.smooth_loss = -np.log(1.0/self.vocab_size)*len(input) # loss at iteration 0
            #from before: SHOULD THE NET EVER BE RESET? WHEN?
            self.hprev = np.zeros((self.hidden_size,1)) # reset RNN memory
        
        inputs = input[0:len(input)-2]
        targets = input[1:len(input)-1]

        # sample from the model now and then
        sample_ix = self.sample(self.hprev, inputs[0], len(input))

        # forward seq_length characters through the net and fetch gradient
        loss, dWxh, dWhh, dWhy, dbh, dby, self.hprev = self.lossFun(inputs, targets, self.hprev)
        self.smooth_loss = self.smooth_loss * 0.999 + loss * 0.001
        if self.n % 100 == 0: print 'iter %d, loss: %f' % (self.n, self.smooth_loss) # print progress

        # perform parameter update with Adagrad
        for param, dparam, mem in zip([self.Wxh, self.Whh, self.Why, self.bh, self.by], 
                                      [dWxh, dWhh, dWhy, dbh, dby], 
                                      [self.mWxh, self.mWhh, self.mWhy, self.mbh, self.mby]):
          mem += dparam * dparam
          param += -self.learning_rate * dparam / np.sqrt(mem + 1e-8) # adagrad update

        self.n += 1 # iteration counter
        
        return sample_ix
    
    def lossFun(self, inputs, targets, hprev):
      """
      inputs,targets are both list of integers.
      hprev is Hx1 array of initial hidden state
      returns the loss, gradients on model parameters, and last hidden state
      """
      xs, hs, ys, ps = {}, {}, {}, {}
      hs[-1] = np.copy(hprev)
      loss = 0
      # forward pass
      for t in xrange(len(inputs)):
        xs[t] = np.zeros((self.vocab_size,1)) # encode in 1-of-k representation
        xs[t][inputs[t]] = 1
        hs[t] = np.tanh(np.dot(self.Wxh, xs[t]) + np.dot(self.Whh, hs[t-1]) + self.bh) # hidden state
        ys[t] = np.dot(self.Why, hs[t]) + self.by # unnormalized log probabilities for next chars
        ps[t] = np.exp(ys[t]) / np.sum(np.exp(ys[t])) # probabilities for next chars
        loss += -np.log(ps[t][targets[t],0]) # softmax (cross-entropy loss)
      # backward pass: compute gradients going backwards
      dWxh, dWhh, dWhy = np.zeros_like(self.Wxh), np.zeros_like(self.Whh), np.zeros_like(self.Why)
      dbh, dby = np.zeros_like(self.bh), np.zeros_like(self.by)
      dhnext = np.zeros_like(hs[0])
      for t in reversed(xrange(len(inputs))):
        dy = np.copy(ps[t])
        dy[targets[t]] -= 1 # backprop into y
        dWhy += np.dot(dy, hs[t].T)
        dby += dy
        dh = np.dot(self.Why.T, dy) + dhnext # backprop into h
        dhraw = (1 - hs[t] * hs[t]) * dh # backprop through tanh nonlinearity
        dbh += dhraw
        dWxh += np.dot(dhraw, xs[t].T)
        dWhh += np.dot(dhraw, hs[t-1].T)
        dhnext = np.dot(self.Whh.T, dhraw)
      for dparam in [dWxh, dWhh, dWhy, dbh, dby]:
        np.clip(dparam, -5, 5, out=dparam) # clip to mitigate exploding gradients
      return loss, dWxh, dWhh, dWhy, dbh, dby, hs[len(inputs)-1]
    
    def sample(self, h, seed_ix, n):
      """ 
      sample a sequence of integers from the model 
      h is memory state, seed_ix is seed letter for first time step
      """
      x = np.zeros((self.vocab_size, 1))
      x[seed_ix] = 1
      ixes = []
      for t in xrange(n):
        h = np.tanh(np.dot(self.Wxh, x) + np.dot(self.Whh, h) + self.bh)
        y = np.dot(self.Why, h) + self.by
        p = np.exp(y) / np.sum(np.exp(y))
        ix = np.random.choice(range(self.vocab_size), p=p.ravel())
        x = np.zeros((self.vocab_size, 1))
        x[ix] = 1
        ixes.append(ix)
      return ixes




class LiveDoubleRNN():
    
    def __init__(self):
        self.maxTime = 10.0 #sec
        self.parameterRNN = LiveByteRNN()
        self.valueChangeRNN = LiveByteRNN()
        self.resetTrainingData()
        self.thread = Thread( target = self.startTrainingAndSamplingLoop )
        self.thread.start()
    
    def resetTrainingData(self):
        self.currentParameterInput = []
        self.currentValueChangeInput = []
        self.previousTime = None
        self.previousParameter = None
        self.previousValue = None
    
    def startTrainingAndSamplingLoop(self):
        self.isRunning = True
        i = 0
        while self.isRunning:
            #once input large enough
            if len(self.currentParameterInput) > 100:
                #learn in chunks
                if i < len(self.currentParameterInput)-24:
                    currentParameterChunk = self.currentParameterInput[i:i+24]
                    currentValueChangeChunk = self.currentValueChangeInput[i:i+24]
                    currentParameterSample = self.parameterRNN.learnAndSample(currentParameterChunk)
                    currentValueChangeSample = self.valueChangeRNN.learnAndSample(currentValueChangeChunk)
                    if (self.isPlaying):
                        print currentParameterSample, currentValueChangeSample
                #restart in beginning of input
                else:
                    i = 0
    
    def toggleListening(self):
        self.isListening = not self.isListening
        if not self.isListening:
            self.resetTrainingData()
        return self.isListening
    
    def togglePlaying():
        self.isPlaying = not self.isPlaying
        return self.isPlaying
    
    def setValue(self, parameter, deltaValue):
        if self.isListening:
            currentTime = time.time()
            if self.previousTime is not None:
                deltaTime = currentTime-self.previousTime
                valueChangeByte = self.valueChangeToByte(deltaValue, deltaTime)
                self.currentParameterInput.append(parameter)
                self.currentValueChangeInput.append(valueChangeByte)
            self.previousTime = currentTime
            self.previousParameter = parameter
            self.previousValues[parameter] = value
    
    def getValue(self):
        return [self.parameterRNN.getSample(), self.byteToValueChange(self.valueChangeRNN.getSample())]
    
    def valueChangeToByte(self, deltaValue, deltaTime):
        #3bit for time, 1bit for sign, 3bit for value
        time = 127.0*min(deltaTime,self.maxTime)/self.maxTime #[0,self.maxTime] -> [0,127]
        time = self.toLogBits(time)<<4 #to first 3 bit
        sign = 1 if deltaValue >= 0 else 0 #1 for pos, 0 for neg
        sign = int(str(sign))<<3 #to 4th bit
        value = abs(deltaValue)
        value = self.toLogBits(value) #to last 3 bit
        print time, sign, value, time+sign+value
        return time+sign+value #struct.unpack(i,time+sign+value)]
    
    def byteToValueChange(self, byte):
        time = byte>>4
        sign = byte-(time<<4)>>3
        value = byte-(time<<4)-(sign<<3)
        print time, sign, value
        sign = sign*2-1
        deltaValue = sign*self.fromLogBits(value)
        deltaTime = self.maxTime*self.fromLogBits(time)/127
        return [deltaValue, deltaTime]
    
    def toLogBits(self, value): #value in [0,127]
        return int(round(math.log(value, 2))) #-> [0,7] log
    
    def fromLogBits(self, value): #value in [0,7] log
        return math.pow(2, value) #-> [0,127]

def main():
    LiveByteRNN()
    """rnns = DoubleLiveRNN()
    bytes = rnns.valueChangeToTwoBytes(0, 23, 0.076)
    print rnns.twoBytesToValueChange(bytes)#[10, 5, 2.5, 1.25, 0.625, 0.3125, 0.15075, 0.075])"""
    """rnn = LiveCharRNN()
    MidiListener(rnn)
    rnn.startListening()
    time.sleep(4)
    rnn.stopListening()"""

if __name__ == "__main__":
    main()
