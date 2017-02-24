# alignment-learning-open
Code for agents that learn vocabulary alignments from interactions specified with temporal rules (Vocabulary Alignment in Openly Specified Interactions, AAMAS17))

Includes the following files:

- agents.py: contains the code for different possible agents

- openprot.py: contains methods that handle open protocols. These are divided into:
  * generators: to create random protocols automatically
  * translators: all the methods that handle the translation between the python protocols and NuSMV
  * general methods: to get information about the protocols

- plots.py: code to generate plots
- example.py: a demo showing the behaviour of one agent. Explained now in detail.

It also includes the following folders:

- json: includes the specification of python protocols
- nusmvSpec: contains temporary files with the NuSMV code that the software generates automatically
- results: to save results from experiments

And:

- NuSMV, a software to model check temporal specifications, downloaded from http://nusmv.fbk.eu/

########### The EXAMPLE ##########

The example shows two agents learning an alignment between their vocabularies by interacting with each other. 

When the example is generated, first it generates a vocabulary and a set of protocols. Then it starts the learning experiment, that lets agents interact at most 200 times. This experiment is executed 5 times. The example prints the number of interactions that agents needed to converge to a perfect alignment between their vocabularies.

To execute the example, call 

 --------------   python example.py [-v -p -b] --------------

It accepts 3 parameters:

* -v is the size of the vocabulary. We recommend vocabularies of up to 10 words to keep the running time reasonable for a demo. Defaults to 4.

* -p is the size of the protocol. We recommend protocols of a size similar to the words to see interesting results. Defaults to 8.

* -b determines the verbosity, which can be 0 or 1. If it is 0 it shows only the minimal information described before. Verbosity 1 is designed for debugging and analysis purposes, and it shows the dynamics of the interaction and the agent's alignments in each step. If using 1, we recommend directing the output to another file to improve readability. Defaults to 0. 

The results of the experiment are saved in the folder /results, in a file named "res-*voc*-*prot*". The experiment and shows produces a plot of the results.