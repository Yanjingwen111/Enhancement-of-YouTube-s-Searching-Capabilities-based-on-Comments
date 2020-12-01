stopword_file = open('stopword.txt', 'r')
lines = stopword_file.readlines()

stopword = []

for line in lines:
    stopword.append(line.strip())