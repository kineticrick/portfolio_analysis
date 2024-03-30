#!/usr/bin/env python3

initial_values = [100, 33, 16, 15, 1, 19]

initial_dates = [1, 2, 3, 4, 5, 6]

l = zip(initial_dates, initial_values)

master_list = []

for date, val in l:
    d = {} 
    d["date"] = date
    d["init_val"] = val
    d["remaining_val"] = val
    
    master_list.append(d)

# Sort master_list by date in ascending order
master_list.sort(key=lambda x: x['date'])

sales = [75, 55, 20, 100]

# Algorithm to subtract sales from master_list
for sale in sales:
    for d in master_list:
        if sale >= d["remaining_val"]:
            sale -= d["remaining_val"]
            d["remaining_val"] = 0
        else:
            d["remaining_val"] -= sale
            break
        
for x in master_list:
    print(x)
    print()