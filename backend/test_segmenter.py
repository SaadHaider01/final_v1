from processors.curriculum_segmenter import segment_curriculum

text = """
Department of Information Technology
Some introductory text...

SEMESTER – VIII

Course Name: Cryptography and Network Security
Course Code: PEC-IT801B
Contacts: 3L

Module 1: Introduction to Cryptography
...

Course Name: Hadoop Data
Course Code: PEC-IT802C
Contacts: 2L

Module 1: HDFS
...
"""

segments = segment_curriculum(text)
import json
print(json.dumps(segments, indent=2))
