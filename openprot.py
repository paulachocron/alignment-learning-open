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


class FlexProtocol(Protocol):
	"""In a Flex Protocol, rules have weights"""

	def __init__(self, vocabulary, rules, flexrules, agent1, agent2, name):
		super(FlexProtocol, self).__init__(vocabulary, rules, agent1, agent2, name)
		self.flexrules = flexrules

	def __str__(self):
		return "Language: "+ self.vocabulary.__str__()+"\n Rules:  "+ self.rules.__str__()+"\n FlexRules:  "+ self.flexrules.__str__()
	def __repr__(self):
		return "Language: "+ self.vocabulary.__repr__()+"\n Rules:  "+ self.rules.__repr__()+"\n FlexRules:  "+ self.flezxrules.__str__()


class Rule:
	def __init__(self, positivity):
		self.pos = positivity

class Existential(Rule):
	def __init__(self, term, n, positivity, agent):
		Rule.__init__(self,positivity)
		self.a = term
		self.n = n
		self.ag = agent

	def translate(self, alignment):
		"""Translates the rule according to an alignment"""
		try:
			return Existential(alignment[self.a], self.n, self.pos, self.ag)
		except KeyError:
			print "Incomplete alignment"
			return

	def __str__(self):
		return "Existential('{}',{},{},{})".format(self.a, self.n,self.pos, self.ag)

	def __repr__(self):
		return "Existential('{}',{},{},{})".format(self.a,  self.n, self.pos, self.ag)


class Relation(Rule):

	def __init__(self, a, b, type, positivity, agent,  agentr):
		Rule.__init__(self,positivity)
		self.a = a
		self.b = b	
		self.type = type
		self.ag = agent
		self.agr = agentr

	def translate(self, alignment):
		try:
			return Relation(alignment[self.a], alignment[self.b], self.type, self.pos, self.ag, self.agr)
		except KeyError:
			print "Incomplete alignment"
			return

	def __str__(self):
		return "Relation('{}','{}','{}',{},{},{})".format(self.a, self.b, self.type, self.pos, self.ag, self.agr)

	def __repr__(self):
		return "Relation('{}','{}','{}',{},{},{})".format(self.a, self.b, self.type, self.pos, self.ag, self.agr)



#**#**#**#**#**#**#**#**#**# Generators #**#**#**#**#**#**#**#**#**#

def protocol_generator(vocabulary, size, length, prop_pos, name):
	""" Generates a random protocol with given size and proportion of positive rules """

	size_pos = int(math.ceil(prop_pos * size))
	size_oth = size - size_pos

	failed = True

	while failed:
		rules_pos = []
		choices_pos = generate_pos(vocabulary, int(len(vocabulary)/8) + 1)
		size_pos = min(len(choices_pos),size_pos)
		size_oth = size - size_pos
		choices_oth = generate_oth(vocabulary, int(len(vocabulary)/8) + 1)
		for i in range(size_pos):
			found = False
			while not found:
				if not choices_pos:
					break
				c = random.choice(choices_pos)
				if is_possible_rule(rules_pos, vocabulary, length, c):
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
				if is_possible_rule(rules, vocabulary, length, c):
					rules.append(c)
					found = True
				choices_oth = [r for r in choices_oth if not r ==c]

		if len(rules)==size:
			failed = False

	return Protocol(vocabulary, rules, name)


def flexprotocol_generator(vocabulary, size, flexsize, divergence, length, prop_pos, a1, a2, name):
	"""Generates a flexible protocol, with weighted rules"""
	base = protocol_generator(vocabulary, size, length, prop_pos, a1, a2, name)

	flex = flexrules_generator(vocabulary, flexsize, length, base.rules)

	flexrules = {}
	baserules = {}
	n = flexsize
	d = int(divergence*100)

	for f in flex:
		n -= 1
		cost = random.choice(range(max(5,d-n*95), min(95,d-(n-1)*5)))
		d =  d - cost	
		flexrules[f] = cost/100.0

	for f in base.rules:
		# parametrize also this when we know how it should be....
		pun = random.choice(range(100))
		baserules[f] = pun/100.0

	return FlexProtocol(vocabulary, baserules, flexrules, a1, a2, name)


def flexrules_generator(vocabulary, size, length, base):

	failed = True
	while failed:
		choices = generate_pos(vocabulary, int(len(vocabulary)/8) + 1) + generate_oth(vocabulary, int(len(vocabulary)/8) + 1)
		choices = [r for r in choices if r not in base]
		rules = copy.copy(base)
		flexrules = []

		size = min(len(choices),size)

		for i in range(size):
			found = False
			# hipp = copy.copy(rules_pos)
			while not found:
				if not choices:
					break
				c = random.choice(choices)
				if is_possible_rule(rules, vocabulary, length, c):
					rules.append(c)
					flexrules.append(c)
					found = True
				# hipp.remove(c)
				choices.remove(c)

		if len(flexrules)==size:
			failed = False

	return flexrules

def is_possible_rule(rules, vocabulary, length, rule):
	new_rules = copy.copy(rules)
	new_rules.append(rule)
	return check_sat(new_rules, vocabulary, length)

def generate_pattern_bound(protocol, bound):
	""" Generates a pattern for a given bound.
	Assumes the protocol is satisfiable"""
	pattern = [random.choice([0,1]) for i in range(bound)]
	return pattern

def generate_pos(vocabulary, boundex):
	"""Generates positive rules"""
	ex = [Existential(v,1,1,ag) for v in vocabulary for ag in [0,1]]
	return ex

def generate_oth(vocabulary, boundex):
	"""Generates all other rules"""
	ex = [Existential(v,0,0,ag) for v in vocabulary for ag in [0,1]]
	types = ("correlation","response","before")
	rel0 = [Relation(a,b,t,0,ag, agr)  for t in types for b in vocabulary for a in vocabulary if a!=b for ag in [0,1] for agr in [0,1]]
	rel1 = [Relation(a,b,t,1,ag, agr) for t in types for b in vocabulary for a in vocabulary if a!=b for ag in [0,1] for agr in [0,1]]
	types2 = ("immAfter", "premise")
	rel2a = [Relation(a,b,t,pos,1,0) for t in types2 for pos in [0,1]]
	rel2b = [Relation(a,b,t,pos,0,1) for t in types2 for pos in [0,1]]
	return ex+rel1+rel0+rel2a+rel2b # Ex will be underrepresented, maybe add another one


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
		return(Existential(m.group('a')[:-2],1,1,m.group('a')[-2]))
	m = re.search('G say != (?P<a>.*?)$', ltlspec)
	if m: 
		return(Existential(m.group('a')[:-2],0,0,m.group('a')[-2]))

	raise NameError('Todo mal con: {}'.format(ltlspec))



#**#**#**#**#**#**#**#**#**# NuSMV Interface #**#**#**#**#**#**#**#**#**#

def call_nusmv(module, nam=""):
	""" Calls NuSMV to check the specification in the string module"""
	rnd = random.choice(range(20))
	f = open(os.path.join(__location__, 'nusmvSpec/nusmvSpec{}.smv'.format(name+nam)), 'w+')
	r = open(os.path.join(__location__, 'nusmvSpec/results{}.txt'.format(name+nam)), 'w+')
	f.write(module)
	f.close()

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

def check_sat(rules, vocabulary, bound, interaction=[], name="", mode="partial"):
	ltlspec = protocol2nusmv_sat(rules,mode)
	aux = [['{}0'.format(v),'{}1'.format(v)] for v in vocabulary]
	possible_actions = [item for sublist in aux for item in sublist]
	model = interaction2nusmv(interaction, vocabulary, bound, mode) + '\n'
	err, nr = call_nusmv(model + ltlspec, nam=name)
	# print model
	# print ltlspec
	# if not " is false" in nr:
	# 	print model
	# 	print ltlspec
	if not err:	
		return " is false" in nr
	else:
		return None

def possible_messages(protocol, interaction, bound, agent):
	inter = copy.copy(interaction)
	inter.append((agent,message))
	return [v for v in protocol.vocabulary if check_sat(protocol.rules, protocol.vocabulary, bound, inter)] 

def is_possible(protocol, interaction, message, bound, agent):
	inter = copy.copy(interaction)
	inter.append((agent, message))
	# l = len(interaction)
	return check_sat(protocol.rules, protocol.vocabulary, bound, inter)
	# return check_sat(protocol.rules, protocol.vocabulary,  min(int(l+math.ceil((bound-l)/2)),int(l+2)), inter)

def is_possible_interp(protocol, interaction, message, bound, agent):
	inter = copy.copy(interaction)
	inter.append((agent, message))
	return check_sat(protocol.rules, protocol.vocabulary,  bound, inter, mode="nobound")

def get_violations(rules, vocabulary, interaction, bound, name=''):
	ltlspec = protocol2nusmv_spec(rules)
	model = interaction2nusmv(interaction, vocabulary, bound)
	err, nr = call_nusmv("{}\n{}".format(model,ltlspec),nam=name)
	if not err:
		res = re.findall('-- specification (.*?) is false', nr)
		# print res
		return res

def brokenNonM(protocol, interaction, bound, message=None,agent=None):
	inter = copy.copy(interaction)	
	if message:
		inter.append((agent,message))
	# print interaction
	# print message
	# print inter
	broken = get_violations(protocol.rules, protocol.vocabulary, inter, len(inter))
	if not broken: 
		return []
	else:
		res = [nusmv2rule(r) for r in broken if not isMonotone(nusmv2rule(r))]
		return res

def brokenM(protocol, interaction, bound, name='', message=None, agent=None):
	inter = copy.copy(interaction)
	if not message==None:
		inter.append((agent,message))

	broken = get_violations(protocol.rules, protocol.vocabulary, inter, len(inter), name=name)
	if not broken: 
		return []
	else:
		res = [nusmv2rule(r) for r in broken if isMonotone(nusmv2rule(r))]
		return res

def okNonMyM(protocol, interaction, bound):
	broken = get_violations(protocol.rules, protocol.vocabulary, interaction, bound)
	broken_rules = (nusmv2rule(r) for r in broken)
	return [r for r in protocol.rules if not r in broken_rules]	


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

def conseq(protocol, message):
	""" Returns all the consequences of the message
	"""
	conseq = []
	for r in protocol.rules: 
		if isinstance(r, Relation) and not isMonotone(r) and r.a == message:
			conseq.append(r.b)
	return conseq

def premise(protocol, message):
	""" Returns all the consequences of the message
	"""
	premise = []
	for r in protocol.rules: 
		if isinstance(r, Relation) and not isMonotone(r) and r.b == message:
			premise.append(r.a)
	return premise

def notsaid_premise(protocol,interaction, message):
	""" Returns all the consequences of the message
	"""
	for m in premise(protocol, message): 
		if not said(m, interaction):
			return True
	return False

def is_premise(protocol, message, ag, agr):
	rules = protocol.rules
	for r in rules: 
		if isinstance(r, Relation) and not isMonotone(r) and r.a == message and r.ag == ag and not (r.type in ['before','premise'] and r.pos==1):
			return True
	return False

def is_premise_con(protocol, message, ag, agr):
	rules = protocol.rules
	for r in rules: 
		if isinstance(r, Relation) and r.type in ['before','premise'] and r.pos==1 and r.a == message and r.ag == ag:
			return True
	return False

def is_premise_ot(protocol, message, ag, agr):
	rules = protocol.rules
	for r in rules: 
		if isinstance(r, Relation) and not isMonotone(r) and r.a == message and r.ag == ag and r.agr == agr and not (r.type in ['before','premise'] and r.pos==1):
			return True
	return False

def is_premise_me(protocol, message, ag, agr):
	rules = protocol.rules
	for r in rules: 
		if isinstance(r, Relation) and not isMonotone(r) and r.a == message and r.ag == ag and r.agr == ag:
			return True
	return False

def is_premise_mon(protocol, message, ag, agr):
	rules = protocol.rules
	for r in rules: 
		if isinstance(r, Relation) and r.a == message and r.ag == ag:
			return True
	return False

def is_conseq(protocol, message, agr):
	rules = protocol.rules
	for r in rules: 
		if isinstance(r, Relation) and not isMonotone(r) and r.b == message and  r.agr == agr:
			return True
	return False

def isMonotone(rule):
	return ((isinstance(rule, Existential) and rule.pos==1) or (isinstance(rule, Relation) and rule.type=='response' and rule.pos==1)  or (isinstance(rule, Relation) and rule.type=='correlation' and rule.pos==1))

def said(message, interaction, agent):
	return sum([1 for u in interaction if u[1]==message and u[0]==agent])>0


#**#**#**#**#**#**#**#**#**# Alignments #**#**#**#**#**#**#**#**#**#

def precision_recall(alignment,  reference):
	if not alignment: 
		return 0,0
	else:
		max_alg = {k : max(alignment[k].iteritems(), key=itemgetter(1))[0] for k in alignment.keys()}
		correct = sum(1 for k in alignment.keys() if max_alg[k] == reference[k])
		return (float(correct)/float(len(alignment.keys())), float(correct)/float(len(reference.keys())))

def recall(alignment,  reference):
	if not alignment: 
		return 0
	else:
		max_alg = {k : max(alignment[k].iteritems(), key=itemgetter(1))[0] for k in alignment.keys()}
		correct = [k for k in alignment.keys() if max_alg[k] == reference[k]]
		return float(len(correct))/float(len(reference.keys()))

def translate1(vocabulary):
	return ["{}1".format(v) for v in vocabulary]


#**#**#**#**#**#**#**#**#**# JSON #**#**#**#**#**#**#**#**#**#

class MyJSONEncoder(json.JSONEncoder):
	"""Prints JSON versions of a protocol"""
	def default(self, o):
		return o.__dict__    

# def im_from_doc(document):

def rule_from_json(json_object):
	if 'type' in json_object:
		return Relation(str(json_object['a']),str(json_object['b']),str(json_object['type']),int(json_object['pos']),int(json_object['ag']),int(json_object['agr']))
	elif 'a' in json_object:
		return Existential(str(json_object['a']),int(json_object['n']),int(json_object['pos']),int(json_object['ag']))
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
name = "ae"+str(random.choice(range(50)))


#**#**#**#**#**#**#**#**#**# Some Testing #**#**#**#**#**#**#**#**#**#

prot = Protocol(['o', 'x', 'z', 's'], [Existential('o',0,0,1), Relation('s','o','correlation',1,0,1)], 'test')
prot1 = Protocol(['h', 'l', 'u', 'j', 'n', 'p', 't', 'g'], [Existential('u',1,1,0), Existential('n',1,1,0), Relation('g','h','response',0,1,1), Relation('j','g','correlation',1,0,1), Relation('g','n','response',0,1,1), Relation('u','t','correlation',1,1,1), Relation('t','p','correlation',1,1,1), Relation('t','p','correlation',0,0,1), Relation('h','j','response',1,1,0), Relation('n','t','before',1,1,0), Relation('g','j','correlation',0,0,1), Relation('t','p','before',0,0,0), Relation('p','u','correlation',1,0,1), Relation('l','n','response',1,0,1)], 'miau')
prot2 = Protocol(['o', 's', 'x', 'z'], [Existential('z',1,1,1), Relation('s','x','before',1,1,1), Relation('x','z','correlation',0,1,0), Relation('z','o','correlation',0,1,0), Relation('s','z','before',1,1,0), Relation('z','s','response',0,0,1), Relation('o','x','before',0,0,0), Relation('x','o','before',1,0,0), Relation('x','o','before',0,0,1), Relation('o','s','response',0,1,0)], "test")