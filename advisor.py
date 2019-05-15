import math
from tabulate import tabulate
split = {
	"world": 0.7,
	"em": 0.2,
	"emu sc": 0.1,
}

value = 0
invest = 1000
rounds=100

values = {}
etfs=set(split.keys())
rows = [["iteration", "buy"] + [k for k in sorted(split, key=lambda k: split[k], reverse=True)]]

for i in range(rounds):
	choice, choice_score = {}, 0

	for etf in etfs:
		new_values = dict(values)
		try:
			new_values[etf] += invest
		except KeyError:
			new_values[etf] = invest


		total = sum(v for v in new_values.values())
		percentages = {k: v/total for k, v in new_values.items()}
		diffs = score= {k: (split[k] - percentages.get(k, 0)) for k in split}
		# Euclidian distance of our allocation vector * the weights (1/split)
		score= math.sqrt(sum(1/split[k]*diffs[k]**2 for k in diffs))
		if score < choice_score or not choice:
			choice = new_values
			choice_score = score
			choice_percentages = percentages
			choice_buy = etf
		
		#print("CHOICE", new_values, percentages, diffs, score)


	#print(i+1, "BUY", choice_buy, choice, choice_percentages)
	row = [i + 1, choice_buy ] + ["%s (%.2f%%)" % (choice.get(k, "-"), 100 * choice_percentages.get(k, 0)) for k in sorted(split, key=lambda k: split[k], reverse=True)]
	rows.append(row)
	values = choice

print(tabulate(rows, headers="firstrow"))
