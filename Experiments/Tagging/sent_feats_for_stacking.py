from collections import defaultdict
import numpy as np
import scipy

CAUSAL_REL   = "_CRel"
RESULT_REL   = "_RRel"
CAUSE_RESULT = "_C->R"

__CSL_REL__ = set((CAUSAL_REL, RESULT_REL, CAUSE_RESULT))

def extract_ys_by_code(tags, all_codes, ysByCode):
    for code in all_codes:
        # prevent duplicating codes below, in case these codes are in all_codes
        if code not in __CSL_REL__:
            ysByCode[code].append(1 if code in tags else 0 )

    ysByCode[CAUSAL_REL].append(  1 if  "Causer" in tags and "explicit" in tags else 0)
    ysByCode[RESULT_REL].append(  1 if  "Result" in tags and "explicit" in tags else 0)
    ysByCode[CAUSE_RESULT].append(1 if ("Result" in tags and "explicit" in tags and "Causer" in tags) else 0)

def num_different_tags(pred):
    wds_since_prev = 9999
    new_tag = False
    cnt = 0
    for has_tag in pred:
        if has_tag > 0:
            if wds_since_prev >= 2 and not new_tag:
                cnt += 1
                new_tag = True
            wds_since_prev = 0
        else:
            wds_since_prev += 1
            new_tag = False
    return cnt

def get_sent_feature_for_stacking_from_tagging_model(sent_input_feats, interaction_tags, essays, word_feats, ys_bytag, tag2Classifier, sparse=False, look_back=0):

    # dicts, key = tag, to a 1D array of word-level predictions
    real_num_predictions_bytag = dict()
    predictions_bytag = dict()
    sent_input_feats = set(sent_input_feats)
    for tag in sent_input_feats:

        cls = tag2Classifier[tag]
        if hasattr(cls, "decision_function"):
            real_num_predictions = cls.decision_function(word_feats)
        else:
            real_num_predictions = cls.predict_proba(word_feats)
        predictions = cls.predict(word_feats)
        real_num_predictions_bytag[tag] = real_num_predictions
        predictions_bytag[tag] = predictions


    # features for the sentence level predictions
    td_sent_feats = []
    ys_by_code = defaultdict(list)
    ix = 0
    lst_look_back = range(look_back)
    for essay_ix, essay in enumerate(essays):

        tmp_essays_xs = []
        for sent_ix, taggged_sentence in enumerate(essay.sentences):
            tmp_sentence_xs = []

            # unique
            sent_unique_true_ys = set()
            un_pred_tags = set()
            # ixs into the tagged words
            ixs = range(ix, ix + len(taggged_sentence))
            ix += len(taggged_sentence)

            for tag in ys_bytag.keys():
                ys = ys_bytag[tag][ixs]
                if np.max(ys, axis=0) > 0:
                    sent_unique_true_ys.add(tag)

                if tag not in sent_input_feats:
                    continue

                real_pred = real_num_predictions_bytag[tag][ixs]
                pred = predictions_bytag[tag][ixs]

                assert ys.shape[0] == real_pred.shape[0] == pred.shape[0]
                mx = np.max(real_pred, axis=0)
                mn = np.min(real_pred, axis=0)

                tmp_sentence_xs.append(mx)
                tmp_sentence_xs.append(mn)

                yes_no = np.max(pred)
                tmp_sentence_xs.append(yes_no)

                if yes_no > 0.0:
                    un_pred_tags.add(tag)
                    # for adding 2-way feature combos

            #pairwise interactions (2 way interactions of predicted tags)
            for a in interaction_tags:
                for b in interaction_tags:
                    if b < a:
                        if a in un_pred_tags and b in un_pred_tags:
                            tmp_sentence_xs.append(1)
                        else:
                            tmp_sentence_xs.append(0)

            extract_ys_by_code(sent_unique_true_ys, sent_input_feats, ys_by_code)
            tmp_essays_xs.append(tmp_sentence_xs)
            # end sentence processing

        feats_per_sentence = len(tmp_essays_xs[0])
        blank = [0] * feats_per_sentence

        """ LOOK BACK """
        # Right now this isn't very useful. What we need to do is to add on only concept codes
        # from the previous sentence as additional feats, and possibly interactions between codes
        # in the previous sentence(s) and the current, treating prev sent codes as different to
        # current sent codes (e.g. a 50 in sent -1 is different to a 50 in current sentence)
        for i, sent_feats in enumerate(tmp_essays_xs):
            concat_feats = list(sent_feats)
            offset = -1
            for j in lst_look_back:
                ix = i + offset
                if ix < 0:
                    to_add = blank
                else:
                    to_add = tmp_essays_xs[ix]
                concat_feats.extend(to_add)
                offset -= 1
            td_sent_feats.append(concat_feats)

    for k in ys_by_code.keys():
        ys_by_code[k] = np.asarray(ys_by_code[k])

    assert len(td_sent_feats) == len(ys_by_code[ list(ys_by_code.keys())[0] ])
    if sparse:
        xs = scipy.sparse.csr_matrix(td_sent_feats)
    else:
        xs = np.asarray(td_sent_feats)
    return xs, ys_by_code

# Similar to above, but where we already have the predictions per class
def get_sent_feature_for_stacking_from_multiclass_tagging_model(sent_input_tags, sent_output_tags, interaction_tags, essays, ys_bytag, predictions_bytag, real_num_predictions_bytag, sparse=False, look_back=0):

    # features for the sentence level predictions
    td_sent_feats = []
    ys_by_code = defaultdict(list)
    ix = 0
    lst_look_back = range(look_back)
    sent_input_tags = set(sent_input_tags)
    all_needed_tags = set(list(sent_input_tags) + list(sent_output_tags))

    for essay_ix, essay in enumerate(essays):

        tmp_essays_xs = []
        for sent_ix, taggged_sentence in enumerate(essay.sentences):
            tmp_sentence_xs = []

            # unique
            sent_unique_true_ys = set()
            un_pred_tags = set()
            # ixs into the tagged words
            ixs = range(ix, ix + len(taggged_sentence))
            ix += len(taggged_sentence)

            for tag in all_needed_tags:
                ys = ys_bytag[tag][ixs]
                if np.max(ys, axis=0) > 0:
                    sent_unique_true_ys.add(tag)

                if tag not in sent_input_tags:
                    continue

                pred = predictions_bytag[tag][ixs]

                if real_num_predictions_bytag:
                    real_pred = real_num_predictions_bytag[tag][ixs]
                    assert ys.shape[0] == real_pred.shape[0] == pred.shape[0]
                    mx = np.max(real_pred, axis=0)
                    mn = np.min(real_pred, axis=0)

                    tmp_sentence_xs.append(mx)
                    tmp_sentence_xs.append(mn)

                yes_no = np.max(pred)
                tmp_sentence_xs.append(yes_no)

                if yes_no > 0.0:
                    un_pred_tags.add(tag)
                    # for adding 2-way feature combos

            #pairwise interactions (2 way interactions of predicted tags)
            for a in interaction_tags:
                for b in interaction_tags:
                    if b < a:
                        if a in un_pred_tags and b in un_pred_tags:
                            tmp_sentence_xs.append(1)
                        else:
                            tmp_sentence_xs.append(0)

            extract_ys_by_code(sent_unique_true_ys, ys_bytag.keys(), ys_by_code)
            tmp_essays_xs.append(tmp_sentence_xs)
            # end sentence processing

        feats_per_sentence = len(tmp_essays_xs[0])
        blank = [0] * feats_per_sentence

        """ LOOK BACK """
        # Right now this isn't very useful. What we need to do is to add on only concept codes
        # from the previous sentence as additional feats, and possibly interactions between codes
        # in the previous sentence(s) and the current, treating prev sent codes as different to
        # current sent codes (e.g. a 50 in sent -1 is different to a 50 in current sentence)
        for i, sent_feats in enumerate(tmp_essays_xs):
            concat_feats = list(sent_feats)
            offset = -1
            for j in lst_look_back:
                ix = i + offset
                if ix < 0:
                    to_add = blank
                else:
                    to_add = tmp_essays_xs[ix]
                concat_feats.extend(to_add)
                offset -= 1
            td_sent_feats.append(concat_feats)

    for k in ys_by_code.keys():
        ys_by_code[k] = np.asarray(ys_by_code[k])

    assert len(td_sent_feats) == len(ys_by_code[ys_by_code.keys()[0]])
    if sparse:
        xs = scipy.sparse.csr_matrix(td_sent_feats)
    else:
        xs = np.asarray(td_sent_feats)
    return xs, ys_by_code

def get_sent_tags_from_word_tags(essays, ys_bytag):
    """ For taking a tagging model and using it's preduictions as a sentence classifier
    """
    # features for the sentence level predictions
    ys_by_code = defaultdict(list)
    ix = 0
    for essay_ix, essay in enumerate(essays):
        for sent_ix, taggged_sentence in enumerate(essay.sentences):
            # unique
            sent_unique_true_ys = set()
            # ixs into the tagged words
            ixs = range(ix, ix + len(taggged_sentence))
            ix += len(taggged_sentence)
            for tag in ys_bytag.keys():
                ys = ys_bytag[tag][ixs]
                if np.max(ys, axis=0) > 0:
                    sent_unique_true_ys.add(tag)
            extract_ys_by_code(sent_unique_true_ys, ys_bytag.keys(), ys_by_code)
            # end sentence processing

    for k in ys_by_code.keys():
        ys_by_code[k] = np.asarray(ys_by_code[k])

    return ys_by_code


def get_sent_feature_for_stacking_from_sentence_model(feat_tags, interaction_tags, sentence_feats, tag2Classifier, sparse=False):

    real_num_predictions_bytag = dict()
    predictions_bytag = dict()
    for tag in feat_tags:
        cls = tag2Classifier[tag]
        if hasattr(cls, "decision_function"):
            real_num_predictions = cls.decision_function(sentence_feats)
        else:
            real_num_predictions = cls.predict_proba(sentence_feats)
        predictions = cls.predict(sentence_feats)
        real_num_predictions_bytag[tag] = real_num_predictions
        predictions_bytag[tag] = predictions
        real_num_predictions_bytag[tag] = real_num_predictions

    # features for the sentence level predictions
    tmp_essays_xs = []
    for ix, sent_feats in enumerate(sentence_feats):
        tmp_sentence_xs = []
        un_pred_tags = set()

        for tag in feat_tags:

            real_pred   = real_num_predictions_bytag[tag][ix]
            pred        = predictions_bytag[tag][ix]

            tmp_sentence_xs.append(real_pred)
            tmp_sentence_xs.append(pred)

            if pred > 0.0:
                un_pred_tags.add(tag)
                # for adding 2-way feature combos

        #pairwise interactions (2 way interactions of predicted tags)
        for a in interaction_tags:
            for b in interaction_tags:
                if b < a:
                    if a in un_pred_tags and b in un_pred_tags:
                        tmp_sentence_xs.append(1)
                    else:
                        tmp_sentence_xs.append(0)

        tmp_essays_xs.append(tmp_sentence_xs)
        # end sentence processing
    if sparse:
        xs = scipy.sparse.csr_matrix(tmp_essays_xs)
    else:
        xs = np.asarray(tmp_essays_xs)
    return xs

if __name__ == "__main__":
    def test(arr):
        print(num_different_tags(arr), "->","".join(map(str,arr)))

    test([0,0,1,0,1,1,0])
    test([0,0,1,0,0,1,1,0,0,0,1,1,1])
    test([1,0,0,1])
    test([1,0,0,1,0,0,1,0,0,1])
    test([1,0,1,0,1,0,1])