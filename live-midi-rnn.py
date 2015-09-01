"""
Minimal character-level Vanilla RNN model. Written by Andrej Karpathy (@karpathy)
BSD License
"""
from threading import Thread
import numpy as np
import mido
import time

class LiveCharRNN():
    
    def __init__(self):
        # data I/O
        self.vocab_size = 128

        # hyperparameters
        self.hidden_size = 300 # size of hidden layer of neurons
        self.learning_rate = 0.1
        print self.learning_rate

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
        
        self.resetTrainingData()
        self.isListening = False
        
        self.thread = Thread( target = self.startTrainingAndSamplingLoop )
        self.thread.start()
    
    def startTrainingAndSamplingLoop(self):
        self.isRunning = True
        i = 0
        while self.isRunning:
            #once input large enough
            if len(self.currentInput) > 1000:
                #learn in chunks
                if i < len(self.currentInput)-24:
                    currentChunk = self.currentInput[i:i+24]
                    currentSample = self.learnAndSample(currentChunk)
                    if (self.isPlaying):
                        print currentSample
                #restart in beginning of input
                else:
                    i = 0
    
    def resetTrainingData(self):
        self.currentInput = []
        self.previousTime = None
        self.previousParameter = None
        self.previousValue = None
    
    def toggleListening(self):
        self.isListening = not self.isListening
        if not self.isListening:
            self.previousTime = None
            self.previousParameter = None
            self.previousValue = None
        return self.isListening
    
    def togglePlaying():
        self.isPlaying = not self.isPlaying
        return self.isPlaying
    
    def setValue(self, parameter, value):
        if self.isListening:
            currentTime = time.time()*100
            if self.previousTime is not None:
                min(127, deltaTime = currentTime - self.previousTime)
                #insert previous parameter and value with corresponding duration
                self.currentInput.extend([self.previousParameter, self.previousValue, deltaTime])
            self.previousTime = currentTime
            self.previousParameter = parameter
            self.previousValue = value
    
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

class MidiListener():
    
    def __init__(self, rnn):
        mido.set_backend('mido.backends.rtmidi')
        self.rnn = rnn
        self.thread = Thread( target = self.listenToMidi )
        self.thread.start()
    
    def listenToMidi(self):
        self.isRunning = True
        try:
            self.inport = mido.open_input()
            while self.isRunning:
                msg = self.inport.receive()
                if msg.type == 'note_on':
                    self.rnn.setValue(msg.note)
                if msg.type == 'note_off':
                    self.rnn.setValue(0)
        except IOError as e:
            print e
    
    def stop(self):
        self.isRunning = False
        self.thread.join()

def main():
    rnn = LiveCharRNN()
    MidiListener(rnn)
    rnn.startListening()
    time.sleep(4)
    rnn.stopListening()

if __name__ == "__main__":
    main()
