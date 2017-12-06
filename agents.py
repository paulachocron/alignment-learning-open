import random
import itertools
import copy
import re
import os, sys, getopt
from multiprocessing import Process, Pipe, Queue
from operator import itemgetter
import json
import timeit
import threading
from openprot import *

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

def fscore(a,b):
	return 2*((a*b)/(a+b+0.01))

def softmax(x):
    """Compute softmax values for each sets of scores in x."""
    return np.exp(x) / np.sum(np.exp(x), axis=0)


def runAg(agent, connection, protocol, pattern):
	result = agent.interact(protocol, connection, pattern)
	if verbose:
		print "outcome {}".format(result)
	return

def start_interaction(agent1, agent2, prot1, prot2, pattern):
	""" Starts interaction between two agents"""
	first_conn, second_conn = Pipe()
	# queue = Queue()
	result_1 = []
	result_2 = []

	a1 = threading.Thread(target=runAg, args=(agent1, first_conn, prot1, pattern))
	a2 = threading.Thread(target=runAg, args=(agent2, second_conn, prot2, pattern))

	a1.start()
	a2.start()
	a1.join()
	a2.join()

class Agent(object):
	""" A basic agent, with an id and a vocabulary"""
	def __init__(self, id, vocabulary, dist={}):
		self.id = id
		self.vocabulary = vocabulary
		self.alignment = {}
		self.res = {}
		self.success = []
		self.known = []
		self.interloc = 1-id
		self.choices = []

		if dist != {}:
			for v in dist.keys():
				self.choices.extend([v for i in range(int(dist[v]*10))])
		else:
			self.choices = copy.copy(vocabulary)

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

	def manage_brokens(self, protocol, mappings_made, received, interpretation, interaction, bound, interloc, broken=None):
		"""Manage non-monotonic broken rules"""
		pass

	def choose_utterance(self, protocol, interaction, bound):
		"""Choose a message to utter between the possible ones"""
		random.shuffle(self.choices)
		for utterance in self.choices:
			if is_possibleNM(protocol, interaction, utterance, bound, self.id):
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
				if interpretation == 0 or interpretation==None:
					# print interaction
					connection.send('failed')
					if verbose:
						print "failed by receiver"
					return 0

				self.manage_mon(protocol, interaction, mappings_made, bound,interpretation, received, self.id)
				interaction.append((self.interloc, interpretation))
				if verbose:
					print "interaction: {}".format(interaction)
				connection.send('ok')

		self.manage_monF(protocol, interaction, bound, self.id, mappings_made)
		return 2

	def manage_mon(self, protocol, interaction, mappings_made, bound, interpretation, received, id):
		"""Manage monotonic broken rules"""
		pass

	def manage_monF(self, protocol, interaction, bound, id, mappings_made):
		"""Manage monotonic broken rules"""
		pass

	def choose_interpretation(self,protocol, interaction, message, bound, mappings_made):
		"""Choose an interpretation between the possible ones"""
		possibilities = possible_messagesNM(protocol, interaction, bound, self.id)
		if not possibilities:
			return 0
		pos = random.choice(possibilities)
		return pos

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
					self.alignment[word][v] = 1.0
				else:
					self.alignment[word][v] = 0.2
		else:
			self.alignment[word] = {v : 1.0 for v in self.vocabulary}

		self.alignment[word] = {v : round(self.alignment[word][v],2) for v in self.vocabulary}
		return


class Logical(Agent):
	"""A logical agent that reasons instead of learning"""

	def __init__(self, id, vocabulary):
		self.id = id
		self.vocabulary = vocabulary
		if verbose:
			print "vocabulary {}".format(self.vocabulary)
		# alignment is dictionary of dictionaries.
		self.alignment = {}
		self.res = {}
		self.success = []
		self.assumptionsStr = []
		self.known = []
		self.possible_alignments = [alg for alg in itertools.permutations(list(range(len(vocabulary))),len(vocabulary))]
		self.interloc = 1-self.id
		self.choices = self.vocabulary
		self.mons = 0	
		
	def __str__(self):
		return str(self.id)

	def __repr__(self):
		return str(self.id)

	def initialize(self, word):
		"""Get initial alignment"""
		self.alignment[word] = {v : (1.0/(len(self.vocabulary))) for v in self.vocabulary}
		return
	
	def build_alg(self):
		choice = random.choice(self.possible_alignments)
		self.alignment = {k : {self.vocabulary[choice.index(self.known.index(k))] : 1.0} for k in self.known}
		return


	def interact(self, protocol, connection, pattern):
		interaction = []
		bound = len(pattern)
		mappings_made = {}

		for t in pattern: 
			if t==self.id:
				utterance = self.choose_utterance(protocol, interaction, bound)
				if not utterance:
					connection.send('failed')
					self.alignment = {k : {self.vocabulary[self.possible_alignments[0].index(self.known.index(k))] : 1.0} for k in self.known}
					return 0

				connection.send(utterance)
				if verbose:
					print "Agent {} says {}".format(self.id, utterance)
				interaction.append((self.id, utterance))
				conf = connection.recv()
				if conf == 'failed':
					self.build_alg()
					return 0
			else:
				received = connection.recv()
				if received == 'failed':
					if verbose:
						print "failed by sender"
					self.build_alg()
					return 0		
				if not received in self.known:
					self.known.append(received)

 				interpretation = self.choose_interpretation(protocol, interaction, received, bound, mappings_made)	
				# print "Agent {} interprets {}".format(self.id, interpretation)
				if interpretation == 0:
					connection.send('failed')
					if verbose:
						print "failed by receiver"
					self.build_alg()
					return 0

				interaction.append((self.interloc, interpretation))
				connection.send('ok')

		self.build_alg()
		if check_sat(protocol.rules, protocol.vocabulary, bound, interaction=interaction, name=str(self.id)):
			return 1
		else:
			return 0
	

	def choose_interpretation(self, protocol, interaction, received, bound, mappings_made):
		
		interpretation = None

		if received in mappings_made.keys():
			if is_possibleNM(protocol, interaction, mappings_made[received], bound, self.interloc):
				interpretation = mappings_made[received]
		else:
			for v in [w for w in self.vocabulary if not w in mappings_made.values()]: 

				if (not interpretation) and is_possibleNM(protocol, interaction, v, bound, self.interloc):
					mappings_made[received] = v
					interpretation = v
				else:
					# broken = brokenNonM(protocol, interaction, bound, message=v, agent=self.interloc)
					# if broken:
					self.manage_brokens(protocol, mappings_made, interaction,received, v, bound, self.interloc)
		return interpretation


	def manage_brokens(self, protocol, mappings_made, interaction, received, interpretation, bound, interloc, broken=None):
		
		if not broken:
			broken = brokenNonM(protocol, interaction, bound, interpretation,interloc)
		brokens_by_int = []

		if verbose:	
			print "known {}".format(self.known)
		if verbose:
			print "broken: {}".format(broken)

		for r in broken:		
			if verbose:
				print "Prev: {}".format(prev)
			if isinstance(r, Existential) and r.pos == 0:
				for alg in self.possible_alignments:
					if verbose:
						print alg
					if self.vocabulary[alg.index(self.known.index(received))]==interpretation:
						if verbose:
							print "here existential {} {}".format(received, interpretation)
						self.possible_alignments.remove(alg)
				break

			elif isinstance(r, Relation) and r.pos == 1 and r.type == 'before':
				if (not [x for x in interaction if str(x[0])==str(r.ag)]):
					for alg in self.possible_alignments:
						if verbose:
							print alg
						if self.vocabulary[alg.index(self.known.index(received))]==interpretation:
							if verbose:
								print "here before/premise {} {}".format(received, interpretation)
							self.possible_alignments.remove(alg)
					break
			
			elif isinstance(r, Relation) and r.pos == 1 and (r.type == 'premise' or r.type== 'immAfter'):
				if (interaction==[] or (interaction[-1][0]!=r.ag)):
					for alg in self.possible_alignments:
						if verbose:
							print alg
						if self.vocabulary[alg.index(self.known.index(received))]==interpretation:
							if verbose:
								print "here before/premise {} {}".format(received, interpretation)
							self.possible_alignments.remove(alg)
					break
				else:
					if str(r.agr)==str(self.interloc) and str(r.b)==received and str(interaction[-1][0])==str(self.interloc):
						previ = interaction[-1][1] 
						prevAlg = [p for p in mappings_made.keys() if previ == mappings_made[p]][0]
						brokens_by_int.append((prevAlg,previ))

			elif isinstance(r, Relation) and r.pos == 0 and (r.type == 'correlation'):
				prevAlg = None
				if interpretation == r.a:
					if str(r.agr)==str(self.interloc) and [p for p in mappings_made.keys() if r.b == mappings_made[p]]:
						prevAlg = [p for p in mappings_made.keys() if r.b == mappings_made[p]][0]
						brokens_by_int.append((prevAlg,r.b))
				elif interpretation == r.b:
					if str(r.ag)==str(self.interloc) and [p for p in mappings_made.keys() if r.a == mappings_made[p]]:
						prevAlg = [p for p in mappings_made.keys() if r.a == mappings_made[p]][0]
						brokens_by_int.append((prevAlg,r.a))

			elif isinstance(r, Relation) and r.pos == 0 and str(r.agr)==str(self.interloc) and str(r.ag)==str(self.interloc) and interpretation == r.b and r.type != 'correlation':
				if [p for p in mappings_made.keys() if r.a == mappings_made[p]]:
					prevAlg = [p for p in mappings_made.keys() if r.a == mappings_made[p]][0]
					brokens_by_int.append((prevAlg,r.a))

		brokens_by_int = list(set(brokens_by_int))

		for pair in brokens_by_int:
			for alg in self.possible_alignments:
				if verbose:
						print alg
				if self.vocabulary[alg.index(self.known.index(pair[0]))]==pair[1] and self.vocabulary[alg.index(self.known.index(received))]==interpretation:
					self.possible_alignments.remove(alg)
					if verbose:
						print "here quad {} {} {} {}".format(pair[0], pair[1],received, interpretation)
	
		return


####### Non-Monotonics

class Simple(Agent):
	"""Simple learning agent"""

	def __init__(self, id, vocabulary, mons=0, param = 0.1, dist={}):
		self.parameter = param
		super(Simple,self).__init__(id, vocabulary, dist)
		
	def compute_possibilities(self, received):
		keys = self.alignment[received].keys()
		random.shuffle(keys)
		possibilities = [k for k in sorted(keys, key=lambda x : self.alignment[received][x])]
		possibilities.reverse()
		return possibilities

	def choose_utterance(self, protocol, interaction, bound):
		"""Choose a message to utter between the possible ones"""
		random.shuffle(self.choices)
		for utterance in self.choices:
			if is_possibleNM(protocol, interaction, utterance, bound, self.id):
				return utterance
		return None

	def is_possible_interp(self, protocol, interaction, interpretation, bound):
		broken = brokenNonM(protocol, interaction, bound, interpretation,self.interloc)
		return not broken

	def choose_interpretation(self, protocol, interaction, received, bound, mappings_made):
		perc = 0.3
		if not received in self.alignment.keys():
			random.shuffle(protocol.vocabulary)
			self.initialize(received)
			# self.res[received] = { v : [] for v in self.vocabulary}

		random.shuffle(self.vocabulary)

		possibilities = [k for k in sorted(self.vocabulary, key=self.alignment[received].get)]
		possibilities.reverse()


		interpretationF = 0
		found = False

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
	
		# if received in mappings_made:
		# 	interpretation = mappings_made[received]
		# 	found = True

		for interpretation in possibilities:
			prev = self.alignment[received][interpretation]

			if verbose:
				print "Received {} Interpretation {}".format(received,interpretation)
			
			if self.is_possible_interp(protocol, interaction, interpretation, bound):
				if not found:
					found = True
					interpretationF = interpretation

			else:
				self.punish(received, interpretation, interaction, prev)
				broken = brokenNonM(protocol, interaction, bound, interpretation,self.interloc)

				self.manage_brokens(protocol, mappings_made, received, interpretation, interaction, bound, self.interloc, broken)

		self.normalize(received)

		mappings_made[received] = interpretationF
		if verbose:
			print self.alignment
			print self.res
		return interpretationF

	def punish(self, received, interpretation, interaction, prev):
		if verbose:
			print "punished"
		self.alignment[received][interpretation] -= self.parameter * prev 

	def normalize(self, received):
		for rec in self.alignment.keys():
			sumV = sum(self.alignment[rec].values())
			if not sumV==0:
				for k in self.alignment[rec].keys():
					self.alignment[rec][k] = self.alignment[rec][k] / sumV


class Reasoner(Simple):
	"""A more complex agent"""

	def punish(self, received, interpretation, interaction, prev):
		pass

	def manage_brokens(self, protocol, mappings_made,  received, interpretation, interaction, bound, interloc, broken=None):
		
		if not broken:
			broken = brokenNonM(protocol, interaction, bound, interpretation,interloc)

		if broken and verbose: 
			print "brokens: {}".format(broken)
	
		prev = self.alignment[received][interpretation]	
		brokens_by_int = []
		brokens_no = []

		for r in broken:					
			if verbose:
				print "Prev: {}".format(prev)
			if isinstance(r, Existential) and r.pos == 0:
				if verbose:
					print "here!"
				self.alignment[received][interpretation] -= 1 * self.alignment[received][interpretation]
				break

			elif isinstance(r, Relation) and r.pos == 1 and r.type == 'before':
				if (not [x for x in interaction if str(x[0])==str(r.ag)]):
					if verbose:
						print "here before"
					self.alignment[received][interpretation]  -= 1 * self.alignment[received][interpretation]
					break
			
			elif isinstance(r, Relation) and r.pos == 1 and (r.type == 'premise' or r.type== 'immAfter'):
				if (interaction==[] or (interaction[-1][0]!=r.ag)):
					if verbose:
						print "here premise"
					self.alignment[received][interpretation]  -= 1 * self.alignment[received][interpretation]
					break
				else:
					if str(r.agr)==str(self.interloc) and str(r.b)==received and str(interaction[-1][0])==str(self.interloc):
						previ = interaction[-1][1] 
						prevAlg = [p for p in mappings_made.keys() if previ == mappings_made[p]][0]
						brokens_by_int.append((prevAlg,previ))

			elif isinstance(r, Relation) and r.pos == 0 and (r.type == 'correlation'):
				prevAlg = None
				if interpretation == r.a:
					if str(r.agr)==str(self.interloc) and [p for p in mappings_made.keys() if r.b == mappings_made[p]]:
						prevAlg = [p for p in mappings_made.keys() if r.b == mappings_made[p]][0]
						brokens_by_int.append((prevAlg,r.b))
				elif interpretation == r.b:
					if str(r.ag)==str(self.interloc) and [p for p in mappings_made.keys() if r.a == mappings_made[p]]:
						prevAlg = [p for p in mappings_made.keys() if r.a == mappings_made[p]][0]
						brokens_by_int.append((prevAlg,r.a))

			elif isinstance(r, Relation) and r.pos == 0 and str(r.agr)==str(self.interloc) and str(r.ag)==str(self.interloc) and interpretation == r.b and r.type != 'correlation':
				if [p for p in mappings_made.keys() if r.a == mappings_made[p]]:
					prevAlg = [p for p in mappings_made.keys() if r.a == mappings_made[p]][0]
					brokens_by_int.append((prevAlg,r.a))
			else:
				brokens_no.append(r)

		brokens_by_int = list(set(brokens_by_int))

		sumBr = 0

		if verbose:
			print "brokens by int {}".format(brokens_by_int)
			
		for t in brokens_by_int:
			prevAlg = self.alignment[t[0]][t[1]]
			sumBr += self.alignment[t[0]][t[1]]
			self.alignment[received][interpretation] -= self.alignment[received][interpretation] * prevAlg**2

			if verbose:
				print "pan: {} = {} : - {}".format(received, interpretation,prevAlg*0.2)

		if not brokens_by_int:
			self.alignment[received][interpretation] -= self.alignment[received][interpretation]  * 0.1
			if verbose:
				print "norm: {} = {} : - {}".format(received, interpretation, str(0.3))			
		return


######### Students

class Student(Simple):
	"""A student decides what to say to maximize the information obtained"""
	def choose_utterance(self, protocol, interaction, bound):
		premise = [v for v in self.vocabulary if is_premise(protocol, v, self.id, self.interloc) and not said(v,interaction,self.id)]
		premise_con = [v for v in self.vocabulary if is_premise_con(protocol, v, self.id, self.interloc) and not v in premise]
		rest = [v for v in self.vocabulary if not v in premise and not v in premise_con]

		to_try = premise +premise + premise+premise+rest + rest + premise_con
 		random.shuffle(to_try)

 		if verbose:
	 		print "to_try: {}".format(to_try)
		for utterance in to_try:
			if is_possibleNM(protocol, interaction, utterance, bound, self.id):				
				return utterance

		return 0

class StudentCoop(Simple):
	"""Student that utters messages that are useful for its interlocutor"""
	def choose_utterance(self, protocol, interaction, bound):
		premise = [v for v in self.vocabulary if is_premise(protocol, v, self.id, self.interloc) and not said(v,interaction,self.id)]
		premise_coop = [v for v in self.vocabulary if is_premise(protocol, v, self.id, self.id) and not said(v,interaction,self.id)]
		rest = [v for v in self.vocabulary if not v in premise and not v in premise_coop]

		prems = premise + premise_coop + premise_coop
		premsrest = premise +premise +rest

		to_try = prems + prems + rest  
		random.shuffle(to_try)
		to_try = premise_coop + premsrest
 		if verbose:
	 		print "to_try: {}".format(to_try)
		for utterance in to_try:
			if is_possibleNM(protocol, interaction, utterance, bound, self.id):				
				return utterance
		return 0

class StudentR(Reasoner, Student):
	def choose_utterance(self, protocol, interaction, bound):
		return Student.choose_utterance(self, protocol, interaction, bound)

class StudentCoopR(Reasoner, StudentCoop):
	def choose_utterance(self, protocol, interaction, bound):
		return StudentCoop.choose_utterance(self, protocol, interaction, bound)

############ Alignments

def create_alg_class(agenttype):
	
	class AgentWAlg(agenttype, AgentAlg):
		def __init__(self, id, vocabulary, alignment, param=0.3):
			self.parameter = param
			AgentAlg.__init__(self,id, vocabulary, alignment)

		def initialize(self, word):
			AgentAlg.initialize(self,word)
		
	return AgentWAlg


##### Monotonics
class SimpleMon(Simple):

	def is_possible_interp(protocol, interaction, interpretation, bound):
		return is_possible_mon(protocol, interaction, interpretation, bound,self.interloc)

	def choose_utterance(self, protocol, interaction, bound):
		"""Choose a message to utter between the possible ones"""
		random.shuffle(self.choices)
		for utterance in self.choices:
			if is_possible_mon(protocol, interaction, utterance, bound, self.id):
				return utterance
		return None


class SimpleBound(Simple):

	def choose_utterance(self, protocol, interaction, bound):
		"""Choose a message to utter between the possible ones"""

		random.shuffle(self.choices)
		for utterance in self.choices:
			if is_possible_bound(protocol, interaction, utterance, bound, self.id):
				return utterance
		return None


	def is_possible_interp(protocol, interaction, interpretation, bound):
		return is_possible_bound(protocol, interaction, interpretation, bound,self.interloc)


class SimpleMonPos(SimpleMon):
	"""An agent that handles monotonic rules"""
	def manage_mon(self, protocol, interaction, mappings_made, bound, interpretation, received, id):
		# pass
		broken_prev = []
		if not interaction == []:
			broken_prev = brokenM(protocol, interaction, bound, name=str(id))

		for interpretation in self.vocabulary:
			interaction2 = copy.copy(interaction)
			interaction2.append((1-id, interpretation))
			
			broken = brokenM(protocol, interaction2, bound, name=str(id))
			
			respected = [r for r in broken_prev if not r in broken]
			br = None
			if respected:
				self.alignment[received][interpretation] += 0.05 * self.alignment[received][interpretation]
				if verbose:
					print "monrew: {} {}".format(received, br)
		return


class SimpleMonNeg(SimpleMon):
	def manage_monF(self, protocol, interaction, bound, id, mappings_made):
		# if 1:
		broken = brokenM(protocol, interaction, bound, name=str(id))

		if verbose:
			print "broken mon: {}".format(broken)
		for r in broken:
			
			if isinstance(r, Relation) and int(r.agr)==int(self.interloc):
				br = r.b
			elif isinstance(r, Existential) and int(r.ag)==int(self.interloc):
				br = r.a
			else:
				continue
			for m in mappings_made.keys():

				self.alignment[m][mappings_made[m]] -= 0.05 * self.alignment[m][mappings_made[m]]
				
				if verbose:
					print "pun {} {}".format(m, mappings_made[m])
					print "rew {} {}".format(m, br)
		return


def experimentAgents(outiter, initer, int, vocab, prot, agents, hetp=None, hetr=None, mons = 0, param=0.3, verbosity=0):

	global verbose
	verbose = verbosity

	v0 = vocab
	voc = len(vocab)
	bound = voc + 2

	v1 = translate1(v0)
	alignment = {v0[k] : v1[k] for k in range(len(v0))}

	if not hetp==None:
		alg = [(v, alignment[v],0.9) for v in v0]
		het0 = generate_heterogeneity(alg, v0, v1, hetp,hetr)
		het1 = generate_heterogeneity(alg, v0, v1, hetp,hetr)
		prevAlg0 = {t[1] : {t[0]: t[2]} for t in het0}
		prevAlg1 = {t[0] : {t[1]: t[2]} for t in het1}
	results = []

	protocols = [p for p in range(int)]

	iterations = outiter * initer

	# results for each agent is: curve for each agent, number of convergence, and time
	results = {ag : ([], [], []) for ag in agents}
	resultsfin = {}
	resultsconv = {}
	distri = {"h" : 0.2, "l": 0.2, "u": 0.2, "j": 0.2, "n": 0.2, "p": 0.2, "t": 0.1, "g": 0.1, "a":0.1,"e":0.1,"f":0.1,"d":0.1}
	distri4 = {"o": 0.1, "s":0.3, "x":0.3, "z":0.3}
	distri8 = {"h" : 0.3, "l": 0.3, "u": 0.3, "j": 0.3, "n": 0.3, "p": 0.3, "t": 0.2, "g": 0.2}
	for o in range(outiter):
		patterns = [] 
		for h in range(int):
			# protT = protocol_generator(vocab, prot, bound, 0.1, mons, "{}{}".format(voc,prot)+str(h))
			# # protT = protocol_generator(vocab, prot, bound, 0.1, mons, "{}{}".format(voc,prot)+str(h), vocabulary_dist = distri)
			# js = protT.to_json()
	
			pattern = [0 for i in range(bound/2)] + [1 for i in range(bound-(bound/2))]		
			random.shuffle(pattern)
			patterns.append(pattern)

		for ag in agents:
			
			allTemp0 = []
			allTemp1 = []
			timeTemp = []
			conv = []
			success0 = []
			success1 = []
			# if het:

			for i in range(initer):
				print "Agent {}".format(ag)
				print "\n Iteration: {} : {}".format(o, i)


				if ag=='simple':	
					a0 = Simple(0, v0, param, dist={})
					a1 = Simple(1, v1,  param, dist={})
				if ag=='reasoner':	
					a0 = Reasoner(0, v0, dist={})
					a1 = Reasoner(1, v1, dist={})

				if ag=='student':	
					a0 = Student(0, v0)
					a1 = Student(1, v1)
					# a0 = Student(0, v0, dist={"o":0.4, "s":0.3, "x":0.2, "z":0.1})
					# a1 = Student(1, v1, dist={"o1":0.4, "s1":0.3, "x1":0.2, "z1":0.1})	
				if ag=='studentcoop':	
					a0 = StudentCoop(0, v0)
					a1 = StudentCoop(1, v1)			
				if ag=='studentcoopr':	
					a0 = StudentCoopR(0, v0)
					a1 = StudentCoopR(1, v1)				
				if ag=='studentr':	
					a0 = StudentR(0, v0)
					a1 = StudentR(1, v1)



				elif ag=='simplebound':	
					a0 = SimpleBound(0, v0, mons, param, dist={})
					a1 = SimpleBound(1, v1, mons, param, dist={})	
					# a0 = Simple(0, v0, param, dist={"o":0.4, "s":0.3, "x":0.2, "z":0.1})
					# a1 = Simple(1, v1, param, dist={"o1":0.4, "s1":0.3, "x1":0.2, "z1":0.1})	
				
				elif ag=='simpleAg':	
					a0 = Simple(0, v0)
					a1 = Agent(1, v1)
				elif ag=='reasonerAg':	
					a0 = Reasoner(0, v0)
					a1 = Agent(1, v1)			
				elif ag=='studentAg':	
					a0 = Student(0, v0)
					a1 = Agent(1, v1)
				elif ag=='studentrAg':	
					a0 = StudentR(0, v0)
					a1 = Agent(1, v1)	

				elif ag=='simplemon':	
					a0 = SimpleMon(0, v0)
					a1 = SimpleMon(1, v1)
				elif ag=='simplemonpos':	
					a0 = SimpleMonPos(0, v0)
					a1 = SimpleMonPos(1, v1)
				elif ag=='simplemonneg':	
					a0 = SimpleMonNeg(0, v0)
					a1 = SimpleMonNeg(1, v1)
				elif ag=='Logical':
					a0 = Logical(0, v0)
					a1 = Logical(1, v1)


				elif ag in ['simple_alg','reasoner_alg','student_alg','studentr_alg','studentcoop_alg','studentcoopr_alg']:
					if ag=='simple_alg':
						ClAlAg = create_alg_class(Simple)
					elif ag=='reasoner_alg':
						ClAlAg = create_alg_class(Reasoner)
					elif ag=='student_alg':
						ClAlAg = create_alg_class(Student)
					elif ag=='studentr_alg':
						ClAlAg = create_alg_class(StudentR)
					elif ag=='studentcoop_alg':
						ClAlAg = create_alg_class(StudentCoop)
					elif ag=='studentcoopr_alg':
						ClAlAg = create_alg_class(StudentCoopR)

					a0 = ClAlAg(0, v0, prevAlg0)
					a1 = ClAlAg(1, v1, prevAlg1)

				resultsTemp0 = []
				resultsTemp1 = []
				for j in range(int):
					pattern = patterns[j]
					if verbose:
						print ""
						print ""
						print "Interaction {}".format(j)
					p = protocols[j]
					protocol0 = protocol_from_json('json/jsonPR-'+str(voc)+str(prot)+str(p))
					# protocol0 = protocol_from_json('json/jsonPR-'+str(o)+str(voc)+str(prot)+str(p))
					if verbose:
						print protocol0
					protocol1 = protocol_translator(protocol0, alignment)
			
					start_time = timeit.default_timer()
					start_interaction(a0,a1,protocol0, protocol1, pattern)
					
					prect0,rect0 = precision_recall(a0.alignment, reverseAlg(alignment))
					prect1,rect1 = precision_recall(a1.alignment, alignment)

					# if 1:
					if verbose:
						print ""
						print "Interaction {}".format(j)

						if ag == "Logical":
							print "possible a0: {}".format(len(a0.possible_alignments))
							print "possible a1: {}".format(len(a1.possible_alignments))
							print "len possible a0: {}".format(len(a0.possible_alignments))
							print "len possible a1: {}".format(len(a1.possible_alignments))
							
						else:	
							print "a0: p {} r {} ".format(prect0,rect0)
							print "a1: p {} r {} ".format(prect1,rect1)
						# print a1.alignment

					resultsTemp0.append((prect0,rect0))
					resultsTemp1.append((prect1,rect1))

					if ag=='Logical':
						cond = (len(a0.possible_alignments)==1 and len(a1.possible_alignments)==1)
					elif ag== 'simpleAg' or ag== 'reasonerAg' or ag== 'studentAg' or ag== 'studentrAg':
						cond = (prect0 ==1.0 and rect0 == 1.0)
					else:
						cond = (prect0 ==1.0 and rect0 == 1.0 and prect1 ==1.0 and rect1 == 1.0)

					if cond:
					# if prect0 ==1.0 and rect0 == 1.0 and prect1 ==1.0 and rect1 == 1.0 :
					# if prect0 ==1.0 and rect0 == 1.0:
						results[ag][2].append(j)
						print j
						for h in range(j+1, int):
							resultsTemp0.append((1.0,1.0))
							resultsTemp1.append((1.0,1.0))
						break	
							
				if not cond:
					results[ag][2].append(int*2)
				# results[ag][0].append([fscore(t[0],t[1]) for t in resultsTemp0])		
				# results[ag][1].append([fscore(t[0],t[1]) for t in resultsTemp1])
				results[ag][1].append([fscore(t[0],t[1]) for t in resultsTemp0])		
				results[ag][1].append([fscore(t[0],t[1]) for t in resultsTemp1])

	for ag in agents:
		print "Now results"
		print "Agent {}".format(ag)
		# results0 = [(sum([t[i][0] for t in results[ag][0]])/iterations, sum([t[i][1] for t in results[ag][0]])/iterations) for i in range(int)]
		# results1 = [(sum([t[i][0] for t in results[ag][1]])/iterations, sum([t[i][1] for t in results[ag][1]])/iterations) for i in range(int)]
		convfin = sum(results[ag][2])/float(len(results[ag][2]))
	
		# print "convergence: {}".format(results[ag][2])
		print "av convergence: {}".format(convfin)
		# print "time: {}".format(time)
		# resultsfin[ag] = (results0, results1)
		resultsfin[ag] = results[ag][1]

		resultsconv[ag] = results[ag][2]

	return resultsfin, resultsconv

#-#-#-#-#-#-#-#-#-#-#-#-#-#- EXAMPLES #-#-#-#-#-#-#-#-#-#-#-#-

voc12 = ["h","l", "u", "j", "n", "p", "t", "g","a","e","f","d"]
voc20 = ["h","l", "u", "j", "n", "p", "t", "g","a","e","f","d","b","o","i","c","k","m","r","q","w","x"]
voc8 = ["h", "l", "u", "j", "n", "p", "t", "g"]
voc10 = ["h", "l", "u", "j", "n", "p", "t", "g","a","e"]
voc4 = ["o", "s", "x", "z"]

voc = 4
# prots = [8,10,12,14,16]
# prots = [6,8,10,12,14]
prots = [4]
# prots= [8,10]
hetp=0.2
hetr=0.2

# for o in range(10):
# 	patterns = [] 
# 	for h in range(300):
# 		protT = protocol_generator(voc8, 6, 8, 0.1, 0, "{}{}{}".format(o,str(8),str(6))+str(h))
# 		# protT = protocol_generator(vocab, prot, bound, 0.1, mons, "{}{}".format(voc,prot)+str(h), vocabulary_dist = distri)

# 		js = protT.to_json()


# for hetp in [0.2,0.5,0.8, 1]:
# 	for hetr in [0.2,0.5,0.8, 1]:
# exp = 'algf{}{}'.format(int(hetp*10),int(hetr*10))
exp = 'test'
# exp = 'std'

# for prot in prots:
# 	# res, resconv =  experimentAgents(10,10,300,voc12,prot,['simple', 'reasoner','student','studentr','studentcoop','studentcoopr'], hetp, hetr, mons=0, verbosity=0)
# 	res, resconv =  experimentAgents(10,10,300,voc4,prot,['simple', 'reasoner','student','studentr','studentcoop','studentcoopr'], hetp, hetr, mons=0, verbosity=0)
# 	# res, resconv =  experimentAgents(10,10,300,voc4,prot,['student_alg'], hetp, hetr, mons=0, verbosity=0)
# 	# res, resconv =  experimentAgents(10,10,300,voc8,prot,['Logical'], hetp, hetr, mons=0, verbosity=0)
# 	# res, resconv =  experimentAgents(10,10,300,voc12,prot,['simpleAg', 'reasonerAg', 'studentAg','studentrAg'], hetp=0.8, hetr=0.8, mons=0, verbosity=0)
# 	# res, resconv =  experimentAgents(10,10,300,voc12,prot,['simple_alg', 'reasoner_alg', 'student_alg','studentr_alg','studentcoop_alg', 'studentcoopr_alg'], hetp, hetr, mons=0, verbosity=0)
# 	# res, resconv =  experimentAgents(10,10,300,voc4,prot,['simple_alg', 'reasoner_alg', 'student_alg','studentr_alg','studentcoop_alg', 'studentcoopr_alg'], hetp, hetr, mons=0, verbosity=0)
# 	# res, resconv =  experimentAgents(1,1,100,voc4,prot,['simple_alg'], hetp=0.8, hetr=0.8, mons=0, verbosity=1)
# 	name = '{}_v{}p{}.py'.format(exp,voc,prot)
# 	nameconv = '{}_conv_v{}p{}.py'.format(exp,voc,prot)
# 	# name = 'grr'
# 	resjson = open('results/' + name, 'w+')
# 	resjsonconv = open('results/' + nameconv, 'w+')

# 	for r in res.keys():
# 		resjson.write('a'+exp+r+str(voc)+str(prot)+' =')
# 		resjson.write(json.dumps(res[r]))	
# 		# resjson.write('\n'+exp+r+str(voc)+str(prot)+'b = ')
# 		# resjson.write(json.dumps(res[r]))
# 		resjson.write('\n')

# 		resjsonconv.write('a'+exp+'conv_'+r+str(voc)+str(prot)+' = ')
# 		resjsonconv.write(json.dumps(resconv[r]))	
# 		resjsonconv.write('\n')
# 	resjson.close()
# 	resjsonconv.close()

# experimentLogical(3,3,300,voc8,8, verbosity=0)

######## PROTOCOL GENERATION EXAMPLE
# voc4 = ["o", "s", "x", "z"]
# # # voc10 = ["h", "l", "u", "j", "n", "p", "t", "g","a","e"]
# # # voc16 = ["h", "r", "j", "a", "c", "e", "v", "l", "n", "g", "w", "i", "t", "x", "o", "s"]

# voc4 = ["o", "s", "x", "z"]
# voc4dist = {"o": 0.1, "s":0.3, "x":0.3, "z":0.3}
# for i in range(300):
# 	print i
# 	# protT = protocol_generator(voc4, 6, 6, 0.1, "48"+str(i), dist_neg = {"o" : 0.5, "s" : 0.5})
# 	protT = protocol_generator(voc8, 6, 10, 0.1, 0, "86"+str(i))
# 	js = protT.to_json()

# if __name__ == "__main__":
#    main(sys.argv[1:])