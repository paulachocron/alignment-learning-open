import random
import itertools
import copy
import re
import os, sys, getopt
from multiprocessing import Process, Pipe, Queue
from operator import itemgetter
import json
import subprocess
import collections
import timeit
import math

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))


#**#**#**#**#**#**# Class definitions #**#**#**#**#**#**#

class Protocol(object):
	"""Basic Protocol with rules, vocabulary and name"""
	def __init__(self, vocabulary, rules, name):

		self.vocabulary = vocabulary
		self.rules = rules
		self.name = name

	def __str__(self):
		return "Language: "+ self.vocabulary.__str__()+"\n Rules:  "+ self.rules.__str__()
	def __repr__(self):
		return "Language: "+ self.vocabulary.__repr__()+"\n Rules:  "+ self.rules.__repr__()

	def to_json(self, path = 'json/'):
		f = open(path+'jsonPR-'+self.name, 'w+')		
		f.write(json.dumps(self, cls=MyJSONEncoder))
		f.close()

class Rule:
	def __init__(self, positivity):
		self.pos = positivity

class Existential(Rule):
	def __init__(self, term, positivity, agent):
		Rule.__init__(self,positivity)
		self.a = term
		self.ag = agent

	def satisfied(self, interaction):
		if self.pos==0:
			return not (self.ag, self.a) in interaction
		else:
			return (self.ag, self.a) in interaction

	def translate(self, alignment):
		"""Translates the rule according to an alignment"""
		try:
			return Existential(alignment[self.a], self.pos, self.ag)
		except KeyError:
			print "Incomplete alignment"
			return

	def inverse(self):
		return Existential(self.a, 1-self.pos, self.ag)

	def is_equal(self, rule):
		# print self 
		# print rule
		return isinstance(rule,Existential) and self.a==rule.a and self.pos==rule.pos and str(self.ag)==str(rule.ag)


	def __str__(self):
		return "Existential('{}',{},{})".format(self.a, self.pos, self.ag)

	def __repr__(self):
		return "Existential('{}',{},{})".format(self.a,  self.pos, self.ag)


class Relation(Rule):

	def __init__(self, a, b, type, positivity, agent,  agentr):
		Rule.__init__(self,positivity)
		self.a = a
		self.b = b	
		self.type = type
		self.ag = agent
		self.agr = agentr

	def inverse(self):
		return Relation(self.a, self.b, self.type, 1-self.pos, self.ag,  self.agr)
		

	def satisfied(self, interaction):
		if self.type=='correlation':
			if self.pos==0:
				return (not (self.ag, self.a) in interaction) or (not (self.agr, self.b) in interaction)
			else: 
				return ((not (self.ag, self.a) in interaction) and (not (self.agr, self.b) in interaction)) or ((self.ag, self.a) in interaction and (self.agr, self.b) in interaction)
		
		elif self.type=='before':
			if self.pos==1:
				for i in range(len(interaction)):
					if interaction[i]== (self.agr, self.b):
						if not (self.ag, self.a) in interaction[:i]:
							return False
				return True			
		
			else: 
				for i in range(len(interaction)):
					if interaction[i] == (self.agr, self.b):
						if (self.ag, self.a) in interaction[:i]:
							return False
				return True

		elif self.type=='response':
			if self.pos==1:
				for i in range(len(interaction)):
					if interaction[i] == (self.ag, self.a):
						if not (self.agr, self.b) in interaction[i:]:
							return False
				return True			
			else: 
				for i in range(len(interaction)):
					if interaction[i] == (self.ag, self.a):
						if (self.agr, self.b) in interaction[i:]:
							return False
				return True

		if self.type=='premise':
			if self.pos==1:
				for i in range(len(interaction)):
					if interaction[i] == (self.agr, self.b):
						if (i==0) or not interaction[i-1] == (self.ag, self.a):
							return False
				return True			
			else: 
				for i in range(len(interaction)):
					if interaction[i] ==(self.agr, self.b):
						if (i>0) and interaction[i-1] == (self.ag, self.a):
							return False
				return True

		if self.type=='immAfter':
			if self.pos==1:
				for i in range(len(interaction)):
					if interaction[i] == (self.ag, self.a):
						if (i==len(interaction)-1) or not interaction[i+1] == (self.agr, self.b):
							return False
				return True			
			else: 
				for i in range(len(interaction)):
					if interaction[i] == (self.ag, self.a):
						if (i<len(interaction)-1) and interaction[i+1] == (self.agr, self.b):
							return False
				return True


	def translate(self, alignment):
		try:
			return Relation(alignment[self.a], alignment[self.b], self.type, self.pos, self.ag, self.agr)
		except KeyError:
			print "Incomplete alignment"
			return

	def is_equal(self, rule):
		# print "isinstance {}".format(isinstance(rule, Relation))
		# print "a: {},{}, ? {}".format(self.a, rule.a, self.a == rule.a)
		# print "b: {},{}, ? {}".format(str(self.b), str(rule.b), str(self.b) == str(rule.b))
		# print "type: {},{}, ? {}".format(self.type, rule.type, self.type == rule.type)
		# print "ag: {},{}, ? {}".format(self.ag, rule.ag, str(self.ag) == str(rule.ag))
		# print "agr: {},{}, ? {}".format(self.agr, rule.agr, str(self.agr) == str(rule.agr))
		# print rule
		return isinstance(rule, Relation) and self.type==self.type and self.a==rule.a and self.b==rule.b and self.pos==rule.pos and str(self.ag)==str(rule.ag) and str(self.agr)==str(rule.agr)

	def __str__(self):
		return "Relation('{}','{}','{}',{},{},{})".format(self.a, self.b, self.type, self.pos, self.ag, self.agr)

	def __repr__(self):
		return "Relation('{}','{}','{}',{},{},{})".format(self.a, self.b, self.type, self.pos, self.ag, self.agr)



#**#**#**#**#**#**#**#**#**# Generators #**#**#**#**#**#**#**#**#**#

def protocol_generator(vocabulary, size, length, prop_pos, mons, name, vocabulary_dist = {}, dist_neg = {}):
	""" Generates a random protocol with given size and proportion of positive rules """

	size_pos = int(math.ceil(prop_pos * size))
	size_oth = size - size_pos

	failed = True

	if vocabulary_dist == {}:
		# unif = 1.0 / len(vocabulary)
		# vocabulary_dist = {v : unif for v in vocabulary}
		vocex = vocabulary

	else:
		vocex = []
		for v in vocabulary_dist.keys():
			vocex.extend([v for i in range(int(vocabulary_dist[v]*10))])


	while failed:
		rules_pos = []
		if mons:
			choices_pos = generate_pos_mons(vocex, int(len(vocabulary)/8) + 1)
		else:
			choices_pos = generate_pos(vocex, int(len(vocabulary)/8) + 1)
		size_pos = min(len(choices_pos),size_pos)
		size_oth = size - size_pos
		if mons:
			choices_oth = generate_oth_mons(vocex, int(len(vocabulary)/8) + 1)
		else:
			choices_oth = generate_oth(vocex, int(len(vocabulary)/8) + 1)
		for i in range(size_pos):
			found = False
			while not found:
				if not choices_pos:
					break
				c = random.choice(choices_pos)
				if is_possible_rule(rules_pos, vocabulary, length, c):
				# if not c.inverse() in rules_pos:
					rules_pos.append(c)
					found = True
				choices_pos = [r for r in choices_pos if not r ==c]

		rules = rules_pos
		for i in range(size_oth):
			found = False
			while not found:
				if not choices_oth:
					break
				c = random.choice(choices_oth)
				# if not c.inverse() in rules_pos:
				if is_possible_rule(rules, vocabulary, length, c):
					rules.append(c)
					found = True
				choices_oth = [r for r in choices_oth if not r ==c]


		if len(rules)==size:
			failed = False

	if not dist_neg == {}:
		for k in dist_neg.keys():
			probs = [0 for i in range(int(dist_neg[k]*10))]
			probs.extend(1 for i in range(int((1 - dist_neg[k])*10)))
			res = random.choice(probs)
			if not res:
				rules.append(Existential(k,0,0))
				rules.append(Existential(k,0,1))
				
	return Protocol(vocabulary, rules, name)

def is_possible_rule(rules, vocabulary, length, rule):
	new_rules = copy.copy(rules)
	new_rules.append(rule)
	return check_sat(new_rules, vocabulary, length, name=str(random.choice(range(10))))

def generate_pattern_bound(protocol, bound):
	""" Generates a pattern for a given bound.
	Assumes the protocol is satisfiable"""
	pattern = [random.choice([0,1]) for i in range(bound)]
	return pattern

def generate_pos_mons(vocabulary, boundex):
	"""Generates positive rules"""
	ex = [Existential(v,1,ag) for v in vocabulary for ag in [0,1]]
	return ex

def generate_oth_mons(vocabulary, boundex):
	"""Generates all other rules"""
	ex = [Existential(v,0,ag) for v in vocabulary for ag in [0,1]]
	types = ("correlation","response","before")
	rel0 = [Relation(a,b,t,0,ag, agr)  for t in types for b in vocabulary for a in vocabulary if a!=b for ag in [0,1] for agr in [0,1]]
	rel1 = [Relation(a,b,t,1,ag, agr) for t in types for b in vocabulary for a in vocabulary if a!=b for ag in [0,1] for agr in [0,1]]
	types2 = ("immAfter", "premise")
	rel2a = []
	rel2b = []
	rel2a = [Relation(a,b,t,pos,1,0) for t in types2 for b in vocabulary for a in vocabulary if a!=b for pos in [0,1]]
	rel2b = [Relation(a,b,t,pos,0,1) for t in types2 for b in vocabulary for a in vocabulary if a!=b for pos in [0,1]]
	return ex+rel1+rel0+rel2a+rel2b # Ex will be underrepresented, maybe add another one

def generate_pos(vocabulary, boundex):
	"""Generates positive rules"""
	# ex = [Existential(v,1,ag) for v in vocabulary for ag in [0,1]]
	return []

def generate_oth(vocabulary, boundex):
	"""Generates all other rules"""
	ex = [Existential(v,0,ag) for v in vocabulary for ag in [0,1]]
	types = ["correlation","response"]
	rel0 = [Relation(a,b,t,0,ag, agr)  for t in types for b in vocabulary for a in vocabulary for ag in [0,1] for agr in [0,1]]
	
	types2 = ["premise","immAfter"]
	rel2a = [Relation(a,b,'premise',pos,ag,agr) for b in vocabulary for ag in [0,1] for agr in [0,1] for a in vocabulary for pos in [0,1]]
	rel3 = [Relation(a,b,'before',pos,ag,agr) for b in vocabulary for a in vocabulary for ag in [0,1] for agr in [0,1] for pos in [0,1]]
	rel4a = [Relation(a,b,'immAfter',pos,ag,agr) for b in vocabulary for ag in [0,1] for agr in [0,1] for a in vocabulary for pos in [0,1]]
	rel4b = []
	rel2b = []
	rel2 = rel2a+rel2b+rel4a+rel4b+rel3
	return ex+rel0+rel2 # Ex will be underrepresented, maybe add another one

#**#**#**#**#**#**#**#**#**# Translators Python-NuSMV #**#**#**#**#**#**#**#**#**#

def protocol2nusmv_sat(rules, mode="complete"):
	""" Translates the rules to a specification to check satisfiability"""
	ltlrules = [rule2nusmv(r) for r in rules]
	if mode == "nobound":
		ltlrules.append('F (say = end)')
	if ltlrules:
		return "LTLSPEC ! (" + " & ".join(ltlrules) + ")"
	else:
		return ""


def rule2nusmv(rule):
	""" Translates one rule to its LTLSPEC in NuSMV"""
	ltlspec = ""
	if isinstance(rule, Relation):
		if rule.type == 'correlation':
			if rule.pos:
				ltlspec =  "(F say = {}{} -> F say = {}{})".format(rule.a,rule.ag,rule.b,rule.agr)
			else:
				ltlspec = "(F say = {}{} -> ! F say = {}{})".format(rule.a,rule.ag,rule.b,rule.agr)

		elif rule.type == 'response':
			if rule.pos:
				ltlspec =  "G ((say = {}{}) -> F (say = {}{}))".format(rule.a,rule.ag,rule.b,rule.agr)
			else:
				ltlspec = "G ((say = {}{}) -> ! F (say = {}{}))".format(rule.a,rule.ag,rule.b,rule.agr)

		elif rule.type == 'before':
			if rule.pos:
				ltlspec =  "(((say != {2}{3}) ) U (say = {0}{1}) | G (say != {2}{3}))  ".format(rule.a,rule.ag,rule.b,rule.agr)
			else:
				ltlspec =  "G (F (say = {2}{3}) -> ! (say = {0}{1}))".format(rule.a,rule.ag,rule.b,rule.agr)

		elif rule.type == 'premise':
			if rule.pos:
				ltlspec =  "G (X (say = {2}{3}) -> (say = {0}{1}))".format(rule.a,rule.ag,rule.b,rule.agr)
			else:
				ltlspec = "G (X (say = {2}{3}) -> ! (say = {0}{1}))".format(rule.a,rule.ag,rule.b,rule.agr)

		elif rule.type == 'immAfter':
			if rule.pos:
				ltlspec =  "G ((say = {}{}) -> X (say = {}{}))".format(rule.a,rule.ag,rule.b,rule.agr)
			else:
				ltlspec = "G ((say = {}{}) -> X ! (say = {}{}))".format(rule.a,rule.ag,rule.b,rule.agr)

	elif isinstance(rule, Existential):
			if rule.pos:
				ltlspec =  "F (say = {}{})".format(rule.a,rule.ag)	
			else:
				ltlspec =  "G (say != {}{})".format(rule.a,rule.ag)
	return ltlspec


def interaction2nusmv(interaction, vocabulary, bound, mode = "complete"):
	""" Translates an interaction to a NuSMV model
		Modes are: Complete (finished), Partial (more utterances possible, check sat with bound)
		Nobound (more utterances possible, check general sat)
	"""

	aux = [['{}0'.format(v),'{}1'.format(v)] for v in vocabulary]
	possible_actions = [item for sublist in aux for item in sublist]
	nStates = len(interaction) 
	intercode = ['{}{}'.format(i[1],i[0]) for i in interaction]

	if mode == "nobound":
		bound = nStates

	values = "say : {{begin, end, {} }}; \n".format(', '.join(possible_actions))
	var = "VAR \n{}state  : 0..{}; \n \n".format(values, bound)
	initial = "init(state) := 0;\ninit(say) := begin; \n"

	trans = "TRANS next(state) in state + toint(state<{});\n".format(bound)
	
	#### say transitions
	say = "next(say) := \n case \n"	
	for i in range(nStates):
		say += "state = {} : {}; \n".format(i, intercode[i])

	possible_actions.append('end')	
	if mode == "partial":
		say += "state < {} & say != end: {{ {} }}; \n".format(bound, ", ".join(possible_actions))
	elif mode == "nobound":
		say += "state = {} & say != end: {{ {} }}; \n".format(nStates, ", ".join(possible_actions))	
	say += "TRUE : end; \n esac; \n"

	assign = "ASSIGN \n" + initial + say + trans 

	return "MODULE main \n\n" + var + assign


def protocol2nusmv_spec(rules):
	ltlrules = ("LTLSPEC "+rule2nusmv(r) for r in rules)
	return "\n".join(ltlrules)

def nusmv2rule(ltlspec):
	############## RELATIONS
	m = re.search('(?<!G ) F say = (?P<a>.*?) ->  F (?!\!)say = (?P<b>.*?)\)', ltlspec)
	if m:
		return(Relation(m.group('a')[:-1], m.group('b')[:-1],'correlation',1,m.group('a')[-1], m.group('b')[-1]))
	m = re.search('F say = (?P<a>.*?) -> !\( F say = (?P<b>.*?)\)', ltlspec)
	if m:
		return(Relation(m.group('a')[:-1], m.group('b')[:-1],'correlation',0,m.group('a')[-1], m.group('b')[-1]))
	m = re.search('G \(say = (?P<a>.*?) ->  F (?!\!)say = (?P<b>.*?)\)', ltlspec)
	if m:
		return(Relation(m.group('a')[:-1], m.group('b')[:-1],'response',1,m.group('a')[-1], m.group('b')[-1]))
	m = re.search('G \(say = (?P<a>.*?) -> \!\( F say = (?P<b>.*?)\)', ltlspec)
	if m:
		return(Relation(m.group('a')[:-1], m.group('b')[:-1],'response',0,m.group('a')[-1], m.group('b')[-1]))
	# m = re.search('\(\!\(say = (?P<b>.*?)\)\) U say = (?P<a>.*?)\)', ltlspec)
	m = re.search('\(say != (?P<b>.*?) U say = (?P<a>.*?)\)', ltlspec)
	# m = re.search('\!\(say = (?P<b>.*?)\) U say = (?P<a>.*?)\)', ltlspec)

	if m:
		return(Relation(m.group('a')[:-1], m.group('b')[:-1],'before',1,m.group('a')[-1], m.group('b')[-1]))
	m = re.search('G \( F say = (?P<b>.*?) -> \!\(say = (?P<a>.*?)\)', ltlspec)
	if m:
		return(Relation(m.group('a')[:-1], m.group('b')[:-1],'before',0,m.group('a')[-1], m.group('b')[-1]))
	m = re.search('G \( X say = (?P<b>.*?) -> (?!\!)say = (?P<a>.*?)\)', ltlspec)
	if m:
		return(Relation(m.group('a')[:-1], m.group('b')[:-1],'premise',1,m.group('a')[-1], m.group('b')[-1]))
	m = re.search('G \( X say = (?P<b>.*?) -> \!\(say = (?P<a>.*?)\)', ltlspec)
	if m:
		return(Relation(m.group('a')[:-1], m.group('b')[:-1],'premise',0,m.group('a')[-1], m.group('b')[-1]))
	m = re.search('G \(say = (?P<a>.*?) ->  X (?!\!)say = (?P<b>.*?)\)', ltlspec)
	if m:
		return(Relation(m.group('a')[:-1], m.group('b')[:-1],'immAfter',1,m.group('a')[-1], m.group('b')[-1]))
	m = re.search('G \(say = (?P<a>.*?) ->  X \!\(say = (?P<b>.*?)\)', ltlspec)
	if m:
		return(Relation(m.group('a')[:-1], m.group('b')[:-1],'immAfter',0,m.group('a')[-1], m.group('b')[-1]))
	
	############ EXISTENTIALS
	m = re.search('F say = (?P<a>.*?)$', ltlspec)
	if m:
		return(Existential(m.group('a')[:-2],1,m.group('a')[-2]))
	m = re.search('G say != (?P<a>.*?)$', ltlspec)
	if m: 
		return(Existential(m.group('a')[:-2],0,m.group('a')[-2]))

	raise NameError('Todo mal con: {}'.format(ltlspec))



#**#**#**#**#**#**#**#**#**# NuSMV Interface #**#**#**#**#**#**#**#**#**#

def call_nusmv(module, nam=""):
	""" Calls NuSMV to check the specification in the string module"""
	rnd = random.choice(range(20))
	# print name+nam
	f = open(os.path.join(__location__, 'nusmvSpec/nusmvSpec{}.smv'.format(str(rnd)+nam)), 'w+')
	r = open(os.path.join(__location__, 'nusmvSpec/results{}.txt'.format(str(rnd)+nam)), 'w+')
	f.write(module)
	f.close()

	# print "nam: {}".format(nam)

	# err = os.system("./NuSMV -coi {} >> {}".format(f.name,r.name))
	err = os.system("./NuSMV -coi -df -dynamic -dcx {} > {}".format(f.name, r.name))

	nr = r.read()

	# print module
	# print nr
	if err:
		print module
		print "err"

	r.close()
	return err, nr


#**#**#**#**#**#**#**#**#**# Logical Operations with Protocols #**#**#**#**#**#**#**#**#**#

def check_modelNM(protocol, interaction):
	for r in protocol.rules:
		if not r.satisfied(interaction):
			return False
		else:
			return True 

def get_violationsNM(protocol, interaction):
	viol = []
	for r in protocol.rules:
		if not isMonotone(r):
			if not r.satisfied(interaction):
				viol.append(r)
	return viol

def check_sat(rules, vocabulary, bound, interaction=[], name="", mode="partial"):
	ltlspec = protocol2nusmv_sat(rules,mode)
	aux = [['{}0'.format(v),'{}1'.format(v)] for v in vocabulary]
	possible_actions = [item for sublist in aux for item in sublist]
	model = interaction2nusmv(interaction, vocabulary, bound, mode) + '\n'

	# print "check sat: {}".format(name)
	err, nr = call_nusmv(model + ltlspec, nam=name)

	if not err:	
		return " is false" in nr
	else:
		return None

def possible_messages(protocol, interaction, bound, agent):
	res = []
	for v in protocol.vocabulary:

		inter = copy.copy(interaction)
		inter.append((agent, v))
		if check_sat(protocol.rules, protocol.vocabulary, bound, inter, name=str(agent)):
			res.append(v)
	return res

def possible_messagesNM(protocol, interaction, bound, agent):
	res = []
	for v in protocol.vocabulary:
		if is_possibleNM(protocol, interaction, v, bound, agent):
			res.append(v)
	return res

def is_possible_bound(protocol, interaction, message, bound, agent):
	inter = copy.copy(interaction)
	inter.append((agent, message))
	return check_sat(protocol.rules, protocol.vocabulary, bound, inter, name=str(agent))

def is_possibleNM(protocol, interaction, message, bound, agent):
	inter = copy.copy(interaction)
	inter.append((agent, message))
	# l = len(interaction)
	viols = get_violationsNM(protocol, inter)
	# print viols
	return get_violationsNM(protocol, inter) == []
	# return check_modelNM(protocol, inter)
	# return check_sat(protocol.rules, protocol.vocabulary,  min(int(l+math.ceil((bound-l)/2)),int(l+2)), inter)

def is_possible_mon(protocol, interaction, message, bound, agent):
	inter = copy.copy(interaction)
	inter.append((agent, message))
	return check_sat(protocol.rules, protocol.vocabulary,  bound, inter, name=str(agent), mode="nobound")

def get_violations(rules, vocabulary, interaction, bound, name=''):
	# print "bound : {}".format(bound)
	ltlspec = protocol2nusmv_spec(rules)

	model = interaction2nusmv(interaction, vocabulary, bound)
	# print "get_violations: {}".format(name)
	err, nr = call_nusmv("{}\n{}".format(model,ltlspec),nam=name)
	if not err:
		res = re.findall('-- specification (.*?) is false', nr)
		# print res
		return res

def brokenNonM(protocol, interaction, bound, message=None,agent=None, name=''):
	inter = copy.copy(interaction)	
	if message:
		inter.append((agent,message))
	broken = get_violationsNM(protocol, inter)

	if message:
		broken = [r for r in broken if not (isinstance(r, Relation) and r.type=='immAfter' and r.pos==1 and r.b != message)]

	return broken

def brokenM(protocol, interaction, bound, message=None, agent=None, name=''):
	inter = copy.copy(interaction)	

	# print message
	if not message==None:
		inter.append((agent,message))

	broken = get_violations(protocol.rules, protocol.vocabulary, inter, len(inter), name=name)
	if not broken: 
		return []
	else:
		res = [nusmv2rule(r) for r in broken if isMonotone(nusmv2rule(r))]
		return res

#**#**#**#**#**#**#**#**#**# Other Operations with Protocols #**#**#**#**#**#**#**#**#**#

def reverseAlg(alignment):
	return {alignment[k] : k for k in alignment.keys()}

def protocol_translator(protocol, alignment):
	""" Tranlates a protocol according to an alignment"""
	newrules = [r.translate(alignment) for r in protocol.rules]
	try:
		newvoc = [alignment[v] for v in protocol.vocabulary]
	except KeyError:
		print "Incomplete alignment"
		return
	return Protocol(newvoc, newrules, "name"+"-1")


def is_premise(protocol, message, ag, agr):
	rules = protocol.rules
	for r in rules: 
		if isinstance(r, Relation) and (not isMonotone(r)) and ((r.a == message and r.ag == ag and r.agr == agr and not (r.type in ['before','premise'] and r.pos==1)) or  (type=='correlation' and r.b == message and r.ag == agr and r.agr == ag)):
		# if isinstance(r, Relation) and (not isMonotone(r)) and r.a == message and r.ag == ag and r.agr == agr:
			return True
	return False

def is_premise_con(protocol, message, ag, agr):
	rules = protocol.rules
	for r in rules: 
		if isinstance(r, Relation) and r.type in ['before','premise'] and r.pos==1 and r.a == message and r.ag == ag:
			return True
	return False

def is_premise_mon(protocol, message, ag, agr):
	rules = protocol.rules
	for r in rules: 
		if isinstance(r, Relation) and r.a == message and r.ag == ag:
			return True
	return False

def is_conseq(protocol, message,ag, agr, interaction):
	rules = protocol.rules
	for r in rules: 
		if isinstance(r, Relation) and (not isMonotone(r)) and r.b == message and r.agr == agr and r.ag == ag:
			return True
	return False

def is_conseq_b(protocol, message, agr):
	rules = protocol.rules
	for r in rules: 
		if isinstance(r, Relation) and not isMonotone(r) and r.b == message and r.agr == agr:
			return True
	return False

def isMonotone(rule):
	return ((isinstance(rule, Existential) and rule.pos==1) or (isinstance(rule, Relation) and (rule.type=='response' or rule.type=='correlation') and rule.pos==1))

def said(message, interaction, agent):
	# return sum([1 for u in interaction if u[1]==message and u[0]==agent])>0
	return (agent, message) in interaction


#**#**#**#**#**#**#**#**#**# Alignments #**#**#**#**#**#**#**#**#**#

def generate_alignment(voc1, voc2, per=1, cant=0, confidence=False,forbidden=[]):
	"""Generates a random alignment between vocabularies voc1 and voc2
		Matches are one to one. Matches only up to per% of voc1 (per% if it is not larger than voc2)
		Assumes voc1 and voc2 have no repearted elements
		TODO: Add parametrization of the confidence distribution, and to allow multiple matches for the same word
	"""

	alg = []
	# generate a subset
	to_match = []

	for i in range(int(cant)):
		w = random.choice([x for x in voc1])
		to_match.append(w)

	for w in to_match:
		v = random.choice([x for x in voc2 if not (w,x) in [(a[0],a[1]) for a in forbidden]])
		if confidence:
			c = round(random.uniform(0.4,1),2)
			alg.append((w,v,c))
		else:
			alg.append((w,v))
	return alg


def generate_heterogeneity(alg, voc1, voc2, precision, recall):
	""" Generates an alignment between voc1 and voc2 with the given precision and recall with respect to alg
	Pre: alg is an alignment between voc1 and voc2
	"""
	# precision is #(found matches \cap relevant matches) / # found matches
	# recall is #(found matches \cap relevant matches) / #relevant matches
	# rv = # relevant matches, frm = # found relevant matches, fm = # found matches
	frm = recall * len(alg)
	fm = frm/precision
	prev = random.sample(alg, int(frm))

	new = generate_alignment(voc1,voc2, cant = fm-frm, confidence=(len(alg[0])==3),forbidden=alg)
	
	return prev + new

def myMax(dictionary):
	maxV = max(dictionary.values())
	maxs = [k for k in dictionary.keys() if dictionary[k]==maxV]
	if len(maxs) == 1:
		return maxs[0]
	return None

def precision_recall(alignment,  reference):
	if not alignment: 
		return 0,0
	else:
		max_alg = {k : myMax(alignment[k]) for k in alignment.keys()}
		correct = sum(1 for k in alignment.keys() if max_alg[k] == reference[k])
		return (float(correct)/float(len(alignment.keys())), float(correct)/float(len(reference.keys())))

def translate1(vocabulary):
	return ["{}1".format(v) for v in vocabulary]

def get_pragmatic_alignment(alignment):
	return {k : max(alignment[k].iteritems(), key=itemgetter(1))[0] for k in alignment.keys()}

def get_pragmatic_multialignment(alignment):
	res = {}
	for k in alignment.keys():
		maxv = max(alignment[k].values())
		maxs = [kk for kk in alignment[k].keys() if alignment[k][kk]==maxv]
		res[k] = maxs
	return res


#**#**#**#**#**#**#**#**#**# JSON #**#**#**#**#**#**#**#**#**#

class MyJSONEncoder(json.JSONEncoder):
	"""Prints JSON versions of a protocol"""
	def default(self, o):
		return o.__dict__


class MyJSONEncoderF(json.JSONEncoder):
	"""Prints JSON versions of a protocol"""
	def default(self, o):
		return {str(k): o.__dict__[k] for k in o.__dict__.keys()}  


def rule_from_json(json_object):
	if 'type' in json_object:
		return Relation(str(json_object['a']),str(json_object['b']),str(json_object['type']),int(json_object['pos']),int(json_object['ag']),int(json_object['agr']))
	elif 'a' in json_object:
		return Existential(str(json_object['a']),int(json_object['pos']),int(json_object['ag']))
	elif "rules" in json_object:
		return Protocol([str(v) for v in json_object['vocabulary']],json_object['rules'],json_object['name'])

def protocol_from_json(doc):
	f = open(doc, 'r')
	json_object = f.read()
	# print json_object
	prot = json.JSONDecoder(object_hook = rule_from_json).decode(json_object)
	return prot

#**#**#**#**#**#**#**#**#**# Global Variables #**#**#**#**#**#**#**#**#**#

global name
name = "ae"+str(random.choice(range(20)))


#**#**#**#**#**#**#**#**#**# Some Testing #**#**#**#**#**#**#**#**#**#

# prot = Protocol(['o', 'x', 'z', 's'], [Existential('s',1,0), Relation('z','x','before',1,0,1), Relation('o','x','before',0,0,0), Relation('z','x','correlation',1,1,0), Relation('x','s','correlation',1,0,1), Relation('s','o','response',1,1,1)], 'test')
prot = Protocol(['o', 'x', 'z', 's'], [Existential('s',1,0), Relation('z','x','before',1,0,1)], 'test')
interaction = [(0, 'o'),(1,'o'), (0, 'z')]


# print Relation('o','z','correlation',1,1,0).satisfied(interaction)
# print is_possibleNM(prot, interaction, 'o', 6, 1)

# prot1 = Protocol(['h', 'l', 'u', 'j', 'n', 'p', 't', 'g'], [Existential('u',1,0), Existential('n',1,0), Relation('g','h','response',0,1,1), Relation('j','g','correlation',1,0,1), Relation('g','n','response',0,1,1), Relation('u','t','correlation',1,1,1), Relation('t','p','correlation',1,1,1), Relation('t','p','correlation',0,0,1), Relation('h','j','response',1,1,0), Relation('n','t','before',1,1,0), Relation('g','j','correlation',0,0,1), Relation('t','p','before',0,0,0), Relation('p','u','correlation',1,0,1), Relation('l','n','response',1,0,1)], 'miau')
# prot2 = Protocol(['o', 's', 'x', 'z'], [Existential('z',1,1), Relation('s','x','before',1,1,1), Relation('x','z','correlation',0,1,0), Relation('z','o','correlation',0,1,0), Relation('s','z','before',1,1,0), Relation('z','s','response',0,0,1), Relation('o','x','before',0,0,0), Relation('x','o','before',1,0,0), Relation('x','o','before',0,0,1), Relation('o','s','response',0,1,0)], "test")