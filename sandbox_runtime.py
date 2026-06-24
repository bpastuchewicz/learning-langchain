# SANDBOX_INPUT: bubble 5 3 8 1 2
"""
Instrukcja:
- Podaj w jednej linii nazwę algorytmu sortowania (bubble, insertion, selection, quick, merge) oraz liczby do posortowania, oddzielone spacjami.
- Przykład: bubble 5 3 8 1 2
"""

def bubble_sort(arr):
    n = len(arr)
    res = arr.copy()
    for i in range(n):
        for j in range(0, n-i-1):
            if res[j] > res[j+1]:
                res[j], res[j+1] = res[j+1], res[j]
    return res

def insertion_sort(arr):
    res = arr.copy()
    for i in range(1, len(res)):
        key = res[i]
        j = i - 1
        while j >= 0 and key < res[j]:
            res[j + 1] = res[j]
            j -= 1
        res[j + 1] = key
    return res

def selection_sort(arr):
    res = arr.copy()
    n = len(res)
    for i in range(n):
        min_idx = i
        for j in range(i+1, n):
            if res[j] < res[min_idx]:
                min_idx = j
        res[i], res[min_idx] = res[min_idx], res[i]
    return res

def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr)//2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort(left) + middle + quick_sort(right)

def merge_sort(arr):
    if len(arr) <= 1:
        return arr
    mid = len(arr)//2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    return merge(left, right)

def merge(left, right):
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] < right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result

def sortuj(alg, arr):
    if alg == "bubble":
        return bubble_sort(arr)
    elif alg == "insertion":
        return insertion_sort(arr)
    elif alg == "selection":
        return selection_sort(arr)
    elif alg == "quick":
        return quick_sort(arr)
    elif alg == "merge":
        return merge_sort(arr)
    else:
        raise ValueError("Nieznany algorytm sortowania")

def main():
    dane = input().strip().split()
    if len(dane) < 2:
        print("Podaj algorytm i liczby do posortowania.")
        return
    alg = dane[0].lower()
    try:
        arr = [int(x) for x in dane[1:]]
    except ValueError:
        print("Błąd: podaj poprawne liczby całkowite.")
        return
    try:
        wynik = sortuj(alg, arr)
        print("Posortowana lista:", wynik)
    except ValueError as e:
        print(e)

if __name__ == "__main__":
    main()
