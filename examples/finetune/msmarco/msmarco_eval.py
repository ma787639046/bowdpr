"""
This module computes evaluation metrics for MSMARCO dataset on the ranking task.
Command line:
python msmarco_eval_ranking.py <path_to_reference_file> <path_to_candidate_file>
Creation Date : 06/12/2018
Last Modified : 1/21/2019
Authors : Daniel Campos <dacamp@microsoft.com>, Rutger van Haasteren <ruvanh@microsoft.com>
"""
import sys
import os
import argparse
import pandas as pd

from collections import Counter

MaxMRRRank = 10

def load_reference_from_stream(f):
    """Load Reference reference relevant passages
    Args:f (stream): stream to load.
    Returns:qids_to_relevant_passageids (dict): dictionary mapping from query_id (int) to relevant passages (list of ints).
    """
    qids_to_relevant_passageids = {}
    for l in f:
        try:
            l = l.strip().split('\t')
            qid = int(l[0])
            if qid in qids_to_relevant_passageids:
                pass
            else:
                qids_to_relevant_passageids[qid] = []
            qids_to_relevant_passageids[qid].append(int(l[1]))
        except:
            raise IOError('\"%s\" is not valid format' % l)
    return qids_to_relevant_passageids


def load_reference(path_to_reference):
    """Load Reference reference relevant passages
    Args:path_to_reference (str): path to a file to load.
    Returns:qids_to_relevant_passageids (dict): dictionary mapping from query_id (int) to relevant passages (list of ints).
    """
    with open(path_to_reference, 'r') as f:
        qids_to_relevant_passageids = load_reference_from_stream(f)
    return qids_to_relevant_passageids


def load_candidate_from_stream(f):
    """Load candidate data from a stream.
    Args:f (stream): stream to load.
    Returns:qid_to_ranked_candidate_passages (dict): dictionary mapping from query_id (int) to a list of 1000 passage ids(int) ranked by relevance and importance
    """
    qid_to_ranked_candidate_passages = {}
    for l in f:
        try:
            l = l.strip().split('\t')
            qid = int(l[0])
            pid = int(l[1])
            rank = int(l[2])
            if qid in qid_to_ranked_candidate_passages:
                pass
            else:
                # By default, all PIDs in the list of 1000 are 0. Only override those that are given
                tmp = [0] * 1000
                qid_to_ranked_candidate_passages[qid] = tmp
            qid_to_ranked_candidate_passages[qid][rank - 1] = pid
        except:
            raise IOError('\"%s\" is not valid format' % l)
    return qid_to_ranked_candidate_passages


def load_candidate(path_to_candidate):
    """Load candidate data from a file.
    Args:path_to_candidate (str): path to file to load.
    Returns:qid_to_ranked_candidate_passages (dict): dictionary mapping from query_id (int) to a list of 1000 passage ids(int) ranked by relevance and importance
    """

    with open(path_to_candidate, 'r') as f:
        qid_to_ranked_candidate_passages = load_candidate_from_stream(f)
    return qid_to_ranked_candidate_passages


def quality_checks_qids(qids_to_relevant_passageids, qids_to_ranked_candidate_passages):
    """Perform quality checks on the dictionaries
    Args:
    p_qids_to_relevant_passageids (dict): dictionary of query-passage mapping
        Dict as read in with load_reference or load_reference_from_stream
    p_qids_to_ranked_candidate_passages (dict): dictionary of query-passage candidates
    Returns:
        bool,str: Boolean whether allowed, message to be shown in case of a problem
    """
    message = ''
    allowed = True

    # Create sets of the QIDs for the submitted and reference queries
    candidate_set = set(qids_to_ranked_candidate_passages.keys())
    ref_set = set(qids_to_relevant_passageids.keys())

    # Check that we do not have multiple passages per query
    for qid in qids_to_ranked_candidate_passages:
        # Remove all zeros from the candidates
        duplicate_pids = set(
            [item for item, count in Counter(qids_to_ranked_candidate_passages[qid]).items() if count > 1])

        if len(duplicate_pids - set([0])) > 0:
            message = "Cannot rank a passage multiple times for a single query. QID={qid}, PID={pid}".format(
                qid=qid, pid=list(duplicate_pids)[0])
            allowed = False

    return allowed, message


def compute_metrics(qids_to_relevant_passageids, qids_to_ranked_candidate_passages):
    """Compute MRR metric
    Args:
    p_qids_to_relevant_passageids (dict): dictionary of query-passage mapping
        Dict as read in with load_reference or load_reference_from_stream
    p_qids_to_ranked_candidate_passages (dict): dictionary of query-passage candidates
    Returns:
        dict: dictionary of metrics {'MRR': <MRR Score>}
    """
    all_scores = {}
    MRR = 0
    qids_with_relevant_passages = 0
    ranking = []
    recall_q_top1 = set()
    recall_q_top50 = set()
    recall_q_all = set()

    for qid in qids_to_ranked_candidate_passages:
        if qid in qids_to_relevant_passageids:
            ranking.append(0)
            target_pid = qids_to_relevant_passageids[qid]
            candidate_pid = qids_to_ranked_candidate_passages[qid]
            for i in range(0, MaxMRRRank):
                if candidate_pid[i] in target_pid:
                    MRR += 1.0 / (i + 1)
                    ranking.pop()
                    ranking.append(i + 1)
                    break
            for i, pid in enumerate(candidate_pid):
                if pid in target_pid:
                    recall_q_all.add(qid)
                    if i < 50:
                        recall_q_top50.add(qid)
                    if i == 0:
                        recall_q_top1.add(qid)
                    break
    if len(ranking) == 0:
        raise IOError("No matching QIDs found. Are you sure you are scoring the evaluation set?")

    MRR = MRR / len(qids_to_relevant_passageids)
    recall_top1 = len(recall_q_top1) * 1.0 / len(qids_to_relevant_passageids)
    recall_top50 = len(recall_q_top50) * 1.0 / len(qids_to_relevant_passageids)
    recall_all = len(recall_q_all) * 1.0 / len(qids_to_relevant_passageids)
    all_scores['MRR @10'] = MRR
    all_scores["recall@1"] = recall_top1
    all_scores["recall@50"] = recall_top50
    all_scores["recall@all"] = recall_all
    all_scores['QueriesRanked'] = len(qids_to_ranked_candidate_passages)
    return all_scores


def compute_metrics_from_files(path_to_reference, path_to_candidate, perform_checks=True):
    """Compute MRR metric
    Args:
    p_path_to_reference_file (str): path to reference file.
        Reference file should contain lines in the following format:
            QUERYID\tPASSAGEID
            Where PASSAGEID is a relevant passage for a query. Note QUERYID can repeat on different lines with different PASSAGEIDs
    p_path_to_candidate_file (str): path to candidate file.
        Candidate file sould contain lines in the following format:
            QUERYID\tPASSAGEID1\tRank
            If a user wishes to use the TREC format please run the script with a -t flag at the end. If this flag is used the expected format is
            QUERYID\tITER\tDOCNO\tRANK\tSIM\tRUNID
            Where the values are separated by tabs and ranked in order of relevance
    Returns:
        dict: dictionary of metrics {'MRR': <MRR Score>}
    """

    qids_to_relevant_passageids = load_reference(path_to_reference)
    qids_to_ranked_candidate_passages = load_candidate(path_to_candidate)
    if perform_checks:
        allowed, message = quality_checks_qids(qids_to_relevant_passageids, qids_to_ranked_candidate_passages)
        if message != '': print(message)

    return compute_metrics(qids_to_relevant_passageids, qids_to_ranked_candidate_passages)


def main():
    """Command line:
    python msmarco_eval_ranking.py <path_to_reference_file> <path_to_candidate_file>
    """

    parser = argparse.ArgumentParser()

    parser.add_argument("--working_dir",
                        default="..",
                        type=str,
                        help="condenser_macl working dir")
    parser.add_argument("--path_to_reference",
                        default="metric/qp_reference.all.tsv",
                        type=str,
                        help="")
    parser.add_argument("--path_to_candidate",
                        default="metric/ranking_res",
                        type=str,
                        help="")
    parser.add_argument("--save_folder",
                        type=str,
                        help="")
    parser.add_argument("--prefix",
                        type=str,
                        default="",
                        help="")
    
    args = parser.parse_args()

    # if len(sys.argv) == 3:
    #     path_to_reference = sys.argv[1]
    #     path_to_candidate = sys.argv[2]

    # else:
    #     path_to_reference = 'metric/qp_reference.all.tsv'
    #     path_to_candidate = 'metric/ranking_res'
    #     #print('Usage: msmarco_eval_ranking.py <reference ranking> <candidate ranking>')
    #     #exit()

    metrics = compute_metrics_from_files(args.path_to_reference, args.path_to_candidate)
    print('#####################')
    for metric in sorted(metrics):
        print('{}: {}'.format(metric, metrics[metric]))
    print('#####################')

    pd_results = pd.DataFrame(metrics, index=[0])
    # pd_results.sort_index(axis=1)
    print(pd_results)
    os.makedirs(args.save_folder, exist_ok=True)
    pd_results.to_csv(os.path.join(args.save_folder, f"{args.prefix}results.csv"), index=False)
    pd_results.to_markdown(os.path.join(args.save_folder, f"{args.prefix}results.md"), index=False)


if __name__ == '__main__':
    main()