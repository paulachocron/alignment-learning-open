from agents import experimentAgents
from openprot import protocol_generator
import string
import sys
import random
import getopt, sys
import json
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import seaborn as sns

def fscore(seq):
	return [2*((p[0]*p[1])/(p[0]+p[1]+0.01)) for p in seq]


def main(argv):
	reps = 5
	inters = 200
	vocab = 4
	prot = 8
	verbosity = 0
	agents = ['memory']
	
	global verbose
	verbose = 0

	try:
		opts, args = getopt.getopt(argv,"v:p:b:",["vocabulary=","protocol=","verbosity="])
	except getopt.GetoptError:
		print '-v verbosity'
		sys.exit(2)
	for opt, arg in opts:
		if opt == '-h':
			print '-v verbosity'
			sys.exit()
		if arg:
			if opt in ("-b", "--verbosity"):
				verbose = int(arg)
			if opt in ("-v", "--vocabulary"):
				vocab = int(arg)
			if opt in ("-p", "--protocol"):
				prot = int(arg)
		print "Starting example"

	voc = []
	for i in range(vocab):
		found = False
		v = random.choice(string.lowercase)
		if not v in voc:
			voc.append(v)
			found = True

	print "Generated Vocabulary: {}".format(voc)

	print "Generating Protocols..."

	for i in range(inters):
		protT = protocol_generator(voc, prot, vocab, 0.1, "{}{}{}".format(vocab,prot,str(i)))
		js = protT.to_json()

	print "Created {} protocols with {} rules each".format(inters, prot)

	print "\n Now starting interactions."

	res =  experimentAgents(reps,inters,voc,prot,agents, verbosity= verbose)
	f = open('results/res-'+str(vocab)+'-'+str(prot), 'w+')		
	f.write(json.dumps(res))
	f.close()

	resa0 = res[0][0]
	resa1 = res[0][1]
	tline = [str(x) for x in range(inters)]
	ag1, = plt.plot(tline,[(fscore(resa0)[i]+fscore(resa1)[i])/2.0 for i in range(inters)], 'b-')
	sns.set_style("white")
	plt.legend(loc = 'best', fontsize=18)
	plt.xticks(fontsize=16)
	plt.yticks(fontsize=16)
	# plt.ylabel('F-Score', fontsize=19 )
	plt.xlabel('Interactions', fontsize=19)
	plt.ylabel('F-Score', fontsize=19)

	plt.show()

if __name__ == "__main__":
   main(sys.argv[1:])
