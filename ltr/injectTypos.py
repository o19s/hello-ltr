try:
    from judgments import Judgment, judgmentsFromFile, judgmentsToFile, judgmentsByQid
except ImportError:
    from .judgments import Judgment, judgmentsFromFile, judgmentsToFile, judgmentsByQid

from random import randint
import random


def typoIt(judgmentInFile, judgmentOutFile):
    currJudgments = [judg for judg in judgmentsFromFile(judgmentInFile)]
    lastQid = currJudgments[-1].qid
    judgDict = judgmentsByQid(currJudgments)

    typoJudgments = []
    for qid, judglist in judgDict.items():
        keywords = judglist[0].keywords
        keywordsWTypo = butterfinger(keywords)

        if keywordsWTypo != keywords:
            newQid = lastQid+1
            print("%s => %s" % (keywords, keywordsWTypo))
            lastQid += 1


if __name__ == "__main__":
    typoIt(judgmentInFile='title_judgments.txt', judgmentOutFile=None)


    # Clone a judgment, inject random typos
