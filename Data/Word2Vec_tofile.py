import gensim
import codecs
from gensim.models import Word2Vec
import cPickle as Pickle
from collections import defaultdict
import numpy as np

__BIN_FILE_ = "/Users/simon.hughes/Documents/Dice Data/GoogleNews-vectors-negative300.bin"

import string
def remove_non_ascii(s):
    return filter(lambda x: x in string.printable, s)


def save_vectors_to_text(desired_words, output_file, norm = True, filename = __BIN_FILE_):
    print("Loading Model")
    model = Word2Vec.load_word2vec_format(filename, binary=True)
    print("Loaded")
    v_words = model.vocab.keys()

    #wd2vec = {}
    with open(output_file, "w+") as fout:
        if desired_words:
            desired_words = set(desired_words)

        for i, wd in enumerate(v_words):
            if i % 1000 == 0:
                print(i)

            # for phrases
            wd_key = remove_non_ascii(wd).replace("_", " ").replace("  "," ")
            if desired_words is None or wd in desired_words:
                ix = model.vocab[wd].index
                vector = model.syn0norm[ix] if norm else model.syn0[ix]
                fout.write(wd_key + "|" + ",".join(map(str,vector)) + "\n")

def vectors_to_pickled_dict(desired_words, output_file, norm = True, filename = __BIN_FILE_):
    print("Loading Model")
    model = Word2Vec.load_word2vec_format(filename, binary=True)
    print("Loaded")
    v_words = model.vocab.keys()

    wd2vec = defaultdict(lambda: np.zeros(300))
    if desired_words:
        desired_words = set(desired_words)

    for i, wd in enumerate(v_words):
        if i % 1000 == 0:
            print(i)

        # for phrases
        wd_key = remove_non_ascii(wd).replace("_", " ").replace("  "," ")
        if desired_words is None or wd in desired_words:
            ix = model.vocab[wd].index
            vector = model.syn0norm[ix] if norm else model.syn0[ix]
            wd2vec[wd_key] = vector

    Pickle.dump(wd2vec, output_file)

save_vectors_to_text(None, "/Users/simon.hughes/Documents/Dice Data/GoogleNews-vectors-negative300.txt")