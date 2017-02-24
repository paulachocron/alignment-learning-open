import random
import itertools
import copy
import re
import os, sys, getopt
from multiprocessing import Process, Pipe, Queue
from operator import itemgetter
import json
import timeit
from openprot import *

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

def softmax(x):
    """Compute softmax values for each sets of scores in x."""
    return np.exp(x) / np.sum(np.exp(x), axis=0)

def start_interaction(agent1, agent2, prot1, prot2, pattern):
	""" Starts interaction between two agents"""
	first_conn, second_conn = Pipe()
	queue = Queue()
	result_1 = []
	result_2 = []
	a1 = Interlocutor(agent1, first_conn, queue, prot1, pattern)
  	a2 = Interlocutor(agent2, second_conn, queue, prot2, pattern)

	a1.start()
	a2.start()
  	a1.join()
	a2.join()

	while not queue.empty():
		history = queue.get()
		if agent1.id == history[0]: 
			agent1.update_alignment(history)
			# agent1.update_alignment(history[1], history[2], history[3], history[4], history[5])
		elif agent2.id == history[0]:
			agent2.update_alignment(history)
			# agent2.update_alignment(history[1], history[2], history[3], history[4], history[5])
			
	a1.terminate()
	a2.terminate()


class Interlocutor(Process):
	""" An interlocutor that relates a process with an agent"""
	
	def __init__(self, agent, connection, queue, protocol, pattern):
		super(Interlocutor, self).__init__()
		self.agent = agent
		self.connection = connection
		self.queue = queue
		self.protocol = protocol
		self.pattern = pattern

	def run(self):
		result = self.agent.interact(self.protocol, self.connection, self.pattern)
		if verbose:
			print "outcome {}".format(result)
		success = self.agent.success.append(result)
		# this should also be an agent's method (something like "remember")
		if isinstance(self.agent, Bobi):
			self.queue.put([self.agent.id, self.agent.alignment, self.agent.res, self.agent.success, self.agent.known, self.agent.possible_alignments])
		else:
			self.queue.put([self.agent.id, self.agent.alignment, self.agent.res, self.agent.success])
		return


class Agent(object):
	""" A basic agent, with an id and a vocabulary"""
	def __init__(self, id, vocabulary):
		self.id = id
		self.vocabulary = vocabulary
		self.alignment = {}
		self.res = {}
		self.success = []
		self.known = []
		self.interloc = 1-id

	def __str__(self):
		return str(self.id)

	def __repr__(self):
		return str(self.id)

	def initialize(self, word):
		"""Get initial alignment"""
		# self.alignment[word] = {v : 0 for v in self.vocabulary}
		random.shuffle(self.vocabulary)
		self.alignment[word] = {v : (1.0/(len(self.vocabulary))) for v in self.vocabulary}
		# self.alignment[word] = {v : 0.5 for v in self.vocabulary}
		return

	def best_map(self, foreign):
		maxVal = max(self.alignment[foreign].values())
		if self.alignment[foreign].values().count(maxVal)>1:
			return None
		best = [v for v in self.vocabulary if self.alignment[foreign][v]==maxVal][0]
		return best

	def certainty(self, v):
		"""Measures the difference between possible interpretations for v"""
		values = [self.alignment[k][v] for k in self.alignment.keys()]
		if values:
			maxVal = max(values)
			if values.count(maxVal)>1:
				return 0
			differences = sum([maxVal-val for val in values])/float(len(values))
			return differences
		else:
			return 0

	def manage_brokens(self, mappings_made, broken, received, interpretation, interaction, perc):
		"""Manage non-monotonic broken rules"""
		pass

	def choose_utterance(self, protocol, interaction, bound):
		"""Choose a message to utter between the possible ones"""
		random.shuffle(self.vocabulary)
		for utterance in self.vocabulary:
			if is_possible(protocol, interaction, utterance, bound, self.id):
				return utterance
		return None


	def interact(self, protocol, connection, pattern):
		"""Start an interaction with an agent"""
		interaction = []
		interactionHist = []
		bound = len(pattern)
		mappings_made = {}
		for t in pattern: 
			if t==self.id:
				utterance = self.choose_utterance(protocol, interaction, bound)
				if not utterance:
					# print interaction
					connection.send('failed')
					if verbose:
						print "failed by sender"
					return 0

				connection.send(utterance)
				if verbose:
					print "Agent {} says {}".format(self.id, utterance)
				interaction.append((self.id, utterance))
				interactionHist.append((t, utterance))
				conf = connection.recv()
				if conf == 'failed':
					return 0
			else:
				received = connection.recv()
				if received == 'failed':
					return 0		
				
 				interpretation = self.choose_interpretation(protocol, interaction, received, bound, mappings_made)	
				if verbose:
					print "Agent {} interprets {}".format(self.id, interpretation)
				if interpretation == 0:
					# print interaction
					connection.send('failed')
					if verbose:
						print "failed by receiver"
					return 0
				if interaction:
					broken_prev = brokenM(protocol, interaction, bound, name=str(self.id))
				else:
					broken_prev = []
				interaction.append((self.interloc, interpretation))
				broken = brokenM(protocol, interaction, bound, name=str(self.id))
				if verbose:
					print "interaction: {}".format(interaction)
				self.manage_mon(broken, broken_prev, mappings_made, bound,received)

				interactionHist.append((t, interpretation))
				connection.send('ok')
		return 2

	def manage_mon(self, broken, broken_prev, mappings_made, bound, received):
		"""Manage monotonic broken rules"""
		pass

	def choose_interpretation(self,protocol, interaction, message, bound):
		"""Choose an interpretation between the possible ones"""
		possibilities = possible_messages(protocol, interaction, bound)
		random.choice(possibilities)
		return possibilities		

	def update_alignment(self, history):
		""" Updates the alignment after an interaction"""
		self.alignment = history[1]
		self.res = history[2]
		self.success = history[3]



class AgentAlg(Agent):
	""" An agent with an alignment"""
	def __init__(self, id, vocabulary, alignment):
		super(AgentAlg,self).__init__(id, vocabulary)
		self.prevAlg = alignment
		for w in alignment.keys():
			self.initialize(w)

	def initialize(self, word):

		self.alignment[word] = {}
		if word in self.prevAlg:
			for v in self.vocabulary:
				if v in self.prevAlg[word].keys():
					self.alignment[word][v] = 1.1
				else:
					self.alignment[word][v] = 1.0
		else:
			self.alignment[word] = {v : 1.0 for v in self.vocabulary}

		self.alignment[word] = {v : round(self.alignment[word][v],2) for v in self.vocabulary}
		return


class Simple(Agent):
	"""Simple learning agent"""
	def compute_possibilities(self, received):
		possibilities = [k[0] for k in sorted(self.alignment[received].iteritems(), key=itemgetter(1))]
		possibilities.reverse()
		return possibilities

	def choose_interpretation(self, protocol, interaction, received, bound, mappings_made):
		perc = 0.3
		if not received in self.alignment.keys():
			random.shuffle(protocol.vocabulary)
			self.initialize(received)
			# self.res[received] = { v : [] for v in self.vocabulary}

		possibilities = self.compute_possibilities(received)

		interpretationF = 0
		found = False
		preValue = 0

		if verbose:
			print ""
			print "I am {}".format(self.id)
			print "received: {}".format(received)
			print "alignment {}".format(self.id)
			print self.alignment
			print "mappings_made"
			print mappings_made
			print "interaction"
			print interaction
	
		if received in mappings_made:
			interpretation = mappings_made[received]
			found = True
			preValue = self.alignment[received][interpretation]
			
			if is_possible_interp(protocol, interaction, interpretation, bound,self.interloc):		
				interpretationF = interpretation

		for interpretation in possibilities:
			prev = self.alignment[received][interpretation]

			if not found or (found and preValue==prev):
				if verbose:
					print "Received {} Interpretation {}".format(received,interpretation)
				
				broken = brokenNonM(protocol, interaction, bound, interpretation,self.interloc)
				if is_possible_interp(protocol, interaction, interpretation, bound,self.interloc):
								
				# if not broken:
				# if not get_violations(protocol.rules, protocol.vocabulary, inter, bound):
					if not interpretation in mappings_made.values() and not found:
						found = True
						preValue = prev
						interpretationF = interpretation

					self.reward(received, interpretation, prev)
				else:
					self.punish(received, interpretation, prev)
					self.manage_brokens(mappings_made, broken, received, interpretation, interaction, perc)

		self.normalize(received)

		mappings_made[received] = interpretationF
		if verbose:
			print self.alignment
			print self.res
		return interpretationF	

	def punish(self, received, interpretation, prev):
		self.alignment[received][interpretation] -= 0.3 * prev 

	def reward(self, received, interpretation, prev):
		self.alignment[received][interpretation] += 0.3 * prev 

	def normalize(self, received):
		for rec in self.alignment.keys():
			sumV = sum(self.alignment[rec].values())
			if not sumV==0:
				for k in self.alignment[rec].keys():
					self.alignment[rec][k] = self.alignment[rec][k] / sumV


class Memory(Agent):
	"""An agent that remembers each experience"""
	def choose_utterance(self, protocol, interaction, bound):
		tmp = copy.copy(self.vocabulary)
		random.shuffle(tmp)
		for utterance in tmp:
			if is_possible(protocol, interaction, utterance, bound, self.id):
					return utterance
		return 0

	def choose_interpretation(self, protocol, interaction, received, bound, mappings_made):
		perc = 0.3
		if not received in self.alignment.keys():
			random.shuffle(self.vocabulary)
			self.initialize(received)

		random.shuffle(self.vocabulary)

		possibilities = [k for k in sorted(self.vocabulary, key=self.alignment[received].get)]
		possibilities.reverse()

		interpretationF = 0
		found = False
		preValue = 0

		if verbose:
			print ""
			print "I am {}".format(self.id)
			print "alignment {}".format(self.id)
			print self.alignment
			print "mappings_made"
			print mappings_made
			print "interaction"
			print interaction
	
		if received in mappings_made:

			interpretation = mappings_made[received]
			found = True
			preValue = self.alignment[received][interpretation]

			if is_possible_interp(protocol, interaction, interpretation, bound, self.interloc):		
				interpretationF = interpretation	

		for interpretation in possibilities:
			prev = self.alignment[received][interpretation]


			if verbose:
				print "Received {} Interpretation {}".format(received,interpretation)
			
			if is_possible_interp(protocol, interaction, interpretation, bound, self.interloc):
		
				if not interpretation in mappings_made.values() and not found:
				# if not found:
					found = True
					preValue = prev
					interpretationF = interpretation
			else:
				self.punish(received, interpretation)
				broken = brokenNonM(protocol, interaction, bound, message=interpretation, agent=self.interloc)
				if verbose:
					print "broken: {}".format(broken)
					self.manage_brokens(mappings_made, broken, received, interpretation, interaction, perc)

		mappings_made[received] = interpretationF
		if verbose:
			print self.alignment
		return interpretationF	

	def punish(self, received, interpretation):
		self.alignment[received][interpretation] -= 0.1
		self.alignment[received][interpretation] = round(self.alignment[received][interpretation],3)
					


class MemoryMon(Memory):
	"""An agent with memory that handles monotonic rules"""
	def manage_mon(self, broken, broken_prev, mappings_made, bound, received):
		respected = [r for r in broken_prev if not r in broken]
		br = None
		for r in respected:
			if isinstance(r, Relation) and int(r.agr)==int(self.interloc):
				br = r.b
			elif isinstance(r, Existential) and int(r.ag)==int(self.interloc):
				br = r.a
		if br:
			self.alignment[received][br] += 0.05
		return


class Student(Memory):
	"""A student decides what to say to maximize the information obtained"""
	def choose_utterance(self, protocol, interaction, bound):
		premise = [v for v in self.vocabulary if is_premise(protocol, v, self.id, self.interloc) and not said(v,interaction,self.id)]
		premise_con = [v for v in self.vocabulary if is_premise_con(protocol, v, self.id, self.interloc)]
		rest = [v for v in self.vocabulary if not v in premise and not v in premise_con]
		premise_con = [v for v in premise_con if not v in premise]

		random.shuffle(premise)
		random.shuffle(premise_con)
		random.shuffle(rest)

		to_try = premise + rest + premise_con
 		if verbose:
	 		print "to_try: {}".format(to_try)
		for utterance in to_try:
			if is_possible(protocol, interaction, utterance, bound, self.id):				
				return utterance
		return 0


class StudentMon(MemoryMon, Student):
	"""This student also takes into account the monotonic rules"""
	def choose_utterance(self, protocol, interaction, bound):
		premise = [v for v in self.vocabulary if is_premise(protocol, v, self.id, self.interloc) and not said(v,interaction,self.id)]
		rest = [v for v in self.vocabulary if not v in premise]
		
		random.shuffle(premise)
		random.shuffle(rest)

		to_try = premise + rest

 		if verbose:
	 		print "to_try: {}".format(to_try)
		for utterance in to_try:
			if is_possible(protocol, interaction, utterance, bound, self.id):
				return utterance
		return 0
		

class MemoryAlg(Memory, AgentAlg):
	"""Agent with memory and with an initial alignment"""
	
	def __init__(self, id, vocabulary, alignment):
		# Here the agent is initialized with its own interaction model
		AgentAlg.__init__(self,id, vocabulary, alignment)

	def choose_interpretation(self, protocol, interaction, received, bound, mappings_made):
		# Here the agent is initialized with its own interaction model
		return Memory.choose_interpretation(self, protocol, interaction, received, bound, mappings_made)

	def initialize(self, word):
		# Here the agent is initialized with its own interaction model
		AgentAlg.initialize(self,word)
		return


class StudentAlg(Student, AgentAlg):
	"""A student with an alignment"""
	def __init__(self, id, vocabulary, alignment):
		# Here the agent is initialized with its own interaction model
		AgentAlg.__init__(self,id, vocabulary, alignment)

	def initialize(self, word):
		# Here the agent is initialized with its own interaction model
		AgentAlg.initialize(self,word)
		return

class Bobi(Agent):
	"""A logical agent that reasons instead of learning"""

	def __init__(self, id, vocabulary):
		self.id = id
		self.vocabulary = vocabulary
		# alignment should be a dictionary of dictionaries.
		self.alignment = {}
		self.res = {}
		self.success = []
		self.assumptions = AssumptionSet()
		self.assumptionsStr = []
		self.known = []
		self.possible_alignments = [alg for alg in itertools.permutations(list(range(len(vocabulary))),len(vocabulary))]
		self.interloc = 1-self.id
		# self.algs = {alg : True for alg in possible_alignments}

	def __str__(self):
		return str(self.id)

	def __repr__(self):
		return str(self.id)

	def update_alignment(self, history):
		alignment = history[1]
		self.res = history[2]
		self.success = history[3]
		self.known = history[4]
		self.possible_alignments = history[5]
		self.alignment = {k : {self.vocabulary[self.possible_alignments[0].index(self.known.index(k))] : 1.0} for k in self.known}

	def interact(self, protocol, connection, pattern):
		interaction = []
		interactionHist = []
		bound = len(pattern)
		mappings_made = {}
		self.alignment = random.choice(self.possible_alignments)
		for t in pattern: 
			if t==self.id:
				utterance = self.choose_utterance(protocol, interaction, bound)
				if not utterance:
					print interaction
					connection.send('failed')
					return 0

				connection.send(utterance)
				if verbose:
					print "Agent {} says {}".format(self.id, utterance)
				interaction.append((self.id, utterance))
				interactionHist.append((t, utterance))
				conf = connection.recv()
				if conf == 'failed':
					return 0
			else:
				received = connection.recv()
				if received == 'failed':
					if verbose:
						print "failed by sender"
					return 0		
				if not received in self.known:
					self.known.append(received)

 				interpretation = self.choose_interpretation(protocol, interaction, received, bound, mappings_made, alignment)	
				# print "Agent {} interprets {}".format(self.id, interpretation)
				if interpretation == 0:
					connection.send('failed')
					if verbose:
						print "failed by receiver"
					return 0

				interaction.append((self.interloc, interpretation))
				connection.send('ok')

		if check_sat(protocol.rules, protocol.vocabulary, bound, interaction=interaction, name=str(self.id)):
			return 1
		else:
			return 0
	

	def choose_interpretation(self, protocol, interaction, received, bound, mappings_made, alignment):
		
		interpretation = 0

		if received in mappings_made.keys():
			if is_possible_interp(protocol, interaction, mappings_made[received], bound, self.interloc):
				interpretation = mappings_made[received]
		else:
			for v in [w for w in self.vocabulary if not w in mappings_made.values()]: 
				if interpretation==0 and is_possible_interp(protocol, interaction, v, bound, self.interloc):
					mappings_made[received] = v
					interpretation = v
				else:
					broken = brokenNonM(protocol, interaction, bound, message=v, agent=self.interloc)
					if broken:
						self.manage_brokens(mappings_made, broken, received, v)
		return interpretation

	def manage_brokens(self, mappings_made, broken, received, interpretation):
		brokens_by_int = []

		for r in broken:				
			if isinstance(r, Existential) and r.pos == 0:
				for alg in self.possible_alignments:
					if self.vocabulary[alg.index(self.known.index(received))]==interpretation:
						self.possible_alignments.remove(alg)

			if isinstance(r, Relation) and r.pos == 0 and (r.type == 'correlation'):
				prevAlg = None
				if interpretation == r.a:
					if [p for p in mappings_made.keys() if r.b == mappings_made[p]]:
						prevAlg = [p for p in mappings_made.keys() if r.b == mappings_made[p]][0]
						brokens_by_int.append((prevAlg,r.b))
				elif interpretation == r.b:
					if [p for p in mappings_made.keys() if r.a == mappings_made[p]]:
						prevAlg = [p for p in mappings_made.keys() if r.a == mappings_made[p]][0]
						brokens_by_int.append((prevAlg,r.a))

			if isinstance(r, Relation) and r.pos == 0 and (r.type == 'response' or r.type == 'before'):
				if interpretation == r.b:
					if [p for p in mappings_made.keys() if r.a == mappings_made[p]]:
						prevAlg = [p for p in mappings_made.keys() if r.a == mappings_made[p]][0]
						brokens_by_int.append((prevAlg,r.a))

		brokens_by_int = list(set(brokens_by_int))

		for pair in brokens_by_int:
			for alg in self.possible_alignments:
				if self.vocabulary[alg.index(self.known.index(pair[0]))]==pair[1] and self.vocabulary[alg.index(self.known.index(received))]==interpretation:
					self.possible_alignments.remove(alg)
		return


class Reasoner(Simple):
	"""A more complex agent"""
	def reward(self, received, interpretation, prev):
		self.alignment[received][interpretation] += 0.3*prev*2


	def punish(self, received, interpretation, prev):
		pass

	def normalize(self, received):
		for rec in self.alignment.keys():
			sumV = sum(self.alignment[rec].values())
			if not sumV==0:
				for k in self.alignment[rec].keys():
					self.alignment[rec][k] = self.alignment[rec][k] / sumV


	def manage_brokens(self, mappings_made, broken, received, interpretation, interaction, perc):
		prev = self.alignment[received][interpretation]	
		brokens_by_int = []

		for r in broken:					
			if verbose:
				print "prev: {}".format(prev)
			if isinstance(r, Existential) and r.pos == 0:
				if verbose:
					print "here!"
				self.alignment[received][interpretation] = 0
				break

			if isinstance(r, Relation) and r.pos == 0 and (r.type == 'correlation'):
				prevAlg = None
				if interpretation == r.a:
					if [p for p in mappings_made.keys() if r.b == mappings_made[p]]:
						prevAlg = [p for p in mappings_made.keys() if r.b == mappings_made[p]][0]
						brokens_by_int.append((prevAlg,r.b))
				elif interpretation == r.b:
					if [p for p in mappings_made.keys() if r.a == mappings_made[p]]:
						prevAlg = [p for p in mappings_made.keys() if r.a == mappings_made[p]][0]
						brokens_by_int.append((prevAlg,r.a))

			if isinstance(r, Relation) and r.pos == 0 and (r.type == 'response' or r.type == 'before'):
				if interpretation == r.b:
					if [p for p in mappings_made.keys() if r.a == mappings_made[p]]:
						prevAlg = [p for p in mappings_made.keys() if r.a == mappings_made[p]][0]
						brokens_by_int.append((prevAlg,r.a))


		brokens_by_int = list(set(brokens_by_int))

		if verbose:
			if  brokens_by_int:
				print "brokens by int: {}".format(brokens_by_int)

		sumBr = 0
		for t in brokens_by_int:
			prevAlg = self.alignment[t[0]][t[1]]
			sumBr += self.alignment[t[0]][t[1]]
			if prev>0:
				self.alignment[t[0]][t[1]] -= min(0.9, self.alignment[t[0]][t[1]]* 2) * prev 
				if verbose:
					print "pun: {} = {} : - {}".format(t[0], t[1],str(0.4 * prev))

			if prevAlg>0:
				self.alignment[received][interpretation] -= min(0.9, self.alignment[received][interpretation]*2) * prevAlg
				if verbose:
					print "pan: {} = {} : - {}".format(received, interpretation, str(0.4 * prevAlg))

		if not brokens_by_int:
			self.alignment[received][interpretation] -= self.alignment[received][interpretation]  * perc * 2
			if verbose:
				print "norm: {} = {} : - {}".format(received, interpretation, str(0.2))		
		return


def experimentAgents(iterations, int, vocab, prot, agents, het=None, verbosity=0):

	global verbose
	verbose = verbosity

	v0 = vocab
	voc = len(vocab)
	bound = voc + 2


	v1 = translate1(v0)
	alignment = {v0[k] : v1[k] for k in range(len(v0))}

	results = []

	protocols = [p for p in range(int)]
	patterns = [[0,1] for p in range(bound/2)]
	pattern = [e for l in patterns for e in l]

	for ag in agents:
		print "Agent {}".format(ag)

		allTemp0 = []
		allTemp1 = []
		timeTemp = []
		conv = []
		success0 = []
		success1 = []
		if het:
			prevAlg0 = {t[1] : {t[0]: t[2]} for t in het}
			prevAlg1 = {t[0] : {t[1]: t[2]} for t in het}
		
		for i in range(iterations):
			print "\n Iteration: {}".format(i)
			if ag=='student':	
				a0 = Student(0, v0)
				a1 = Student(1, v1)
			elif ag=='simple':	
				a0 = Simple(0, v0)
				a1 = Simple(1, v1)
			elif ag=='student-mon':	
				a0 = StudentMon(0, v0)
				a1 = StudentMon(1, v1)			
			elif ag=='memory':	
				a0 = Memory(0, v0)
				a1 = Memory(1, v1)
			elif ag=='memorymon':	
				a0 = MemoryMon(0, v0)
				a1 = MemoryMon(1, v1)
			elif ag=='reasoner':	
				a0 = Reasoner(0, v0)
				a1 = Reasoner(1, v1)			
			elif ag=='bobi':	
				a0 = Bobi(0, v0)
				a1 = Bobi(1, v1)
			elif ag=='memory-alg':
				prevAlg0 = {t[1] : {t[0]: t[2]} for t in het}
				prevAlg1 = {t[0] : {t[1]: t[2]} for t in het}
				a0 = MemoryAlg(0, v0, prevAlg0)
				a1 = MemoryAlg(1, v1, prevAlg1)
			elif ag=='student-alg':
				prevAlg0 = {t[1] : {t[0]: t[2]} for t in het}
				prevAlg1 = {t[0] : {t[1]: t[2]} for t in het}
				a0 = StudentAlg(0, v0, prevAlg0)
				a1 = StudentAlg(1, v1, prevAlg1)

			resultsTemp0 = []
			resultsTemp1 = []
			for j in range(int):
				if verbose:
					print "Interaction {}".format(j)
				p = protocols[j]
				protocol0 = protocol_from_json('json/jsonPR-'+str(voc)+str(prot)+str(p))
				if verbose:
					print protocol0
				protocol1 = protocol_translator(protocol0, alignment)
		
				start_time = timeit.default_timer()
				start_interaction(a0,a1,protocol0, protocol1, pattern)
				elapsed = timeit.default_timer() - start_time
				timeTemp.append(elapsed)
				
				prect0,rect0 = precision_recall(a0.alignment, reverseAlg(alignment))
				prect1,rect1 = precision_recall(a1.alignment, alignment)

				if verbose:
					print "Interaction {}".format(j)

					print "a0: p {} r {} ".format(prect0,rect0)
					print "a1: p {} r {} ".format(prect1,rect1)

				resultsTemp0.append((prect0,rect0))
				resultsTemp1.append((prect1,rect1))

				if prect0 ==1.0 and rect0 == 1.0 and prect1 ==1.0 and rect1 == 1.0 :
					conv.append(j)
					print j
					for h in range(j+1, int):
						resultsTemp0.append((1.0,1.0))
						resultsTemp1.append((1.0,1.0))
					break	

			if not (prect0 ==1.0 and rect0 == 1.0 and prect1 ==1.0 and rect1 == 1.0):
				conv.append(int*2)
			allTemp0.append(resultsTemp0)		
			allTemp1.append(resultsTemp1)
			success0.append(a0.success)		
			success1.append(a1.success)		
	        print conv
		
		results0 = [(sum([t[i][0] for t in allTemp0])/iterations, sum([t[i][1] for t in allTemp0])/iterations) for i in range(int)]
		results1 = [(sum([t[i][0] for t in allTemp1])/iterations, sum([t[i][1] for t in allTemp1])/iterations) for i in range(int)]
		convfin = sum(conv)/float(len(conv))
		time = float(sum(timeTemp))/len(timeTemp)

		results.append((results0, results1, conv, convfin, time))

	for r in results:
		print r[2]
		print r[3]

	return results


#-#-#-#-#-#-#-#-#-#-#-#-#-#- EXAMPLES #-#-#-#-#-#-#-#-#-#-#-#-

# verbose = 0

# # print experientConv(1,100)
# voc10 = ["h","l", "u", "j", "n", "p", "t", "g","a","e"]
# v10 = ["h", "l", "u", "j", "n", "p", "t", "g","a","e"]
# v0 = ["o", "s", "x", "z"]
# v8 = ["h", "l", "u", "j", "n", "p", "t", "g"]

# v1 = translate1(v0)
# alignment = {v0[k] : v1[k] for k in range(len(v0))}

# alg = [(v, alignment[v],0.9) for v in v0]
# het = generate_heterogeneity(alg, v0, v1, 1.0,0.5)

# # res =  experimentAgents(5,100,4,8,[3,4,42],het)

# # voc4 = ["o", "s", "x", "z"]
# voc8 = ["h", "l", "u", "j", "n", "p", "t", "g"]
# # # voc10 = ["h", "l", "u", "j", "n", "p", "t", "g","a","e"]
# # # voc16 = ["h", "r", "j", "a", "c", "e", "v", "l", "n", "g", "w", "i", "t", "x", "o", "s"]

# voc4 = ["o", "s", "x", "z"]

# # for i in range(200):
# # 	print i
# # 	protT = protocol_generator(voc4, 10, 6, 0.1, "410b"+str(i))
# # 	js = protT.to_json()

# if __name__ == "__main__":
#    main(sys.argv[1:])