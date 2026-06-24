# SANDBOX_INPUT: 7
def fibonacci_tail(n, a=0, b=1):
    """
    Oblicza n-ty wyraz ciągu Fibonacciego z użyciem rekurencji ogonowej.
    :param n: numer wyrazu (n >= 0)
    :param a: pierwszy akumulator (domyślnie 0)
    :param b: drugi akumulator (domyślnie 1)
    :return: n-ty wyraz ciągu Fibonacciego
    """
    if n == 0:
        return a
    return fibonacci_tail(n - 1, b, a + b)

if __name__ == "__main__":
    try:
        n = int(input("Podaj numer wyrazu ciągu Fibonacciego (n >= 0): "))
        if n < 0:
            print("Numer wyrazu musi być nieujemny.")
        else:
            wynik = fibonacci_tail(n)
            print(f"{n}-ty wyraz ciągu Fibonacciego to: {wynik}")
    except ValueError:
        print("Podano nieprawidłową wartość.")

# Instrukcja:
# Uruchom skrypt i podaj numer wyrazu ciągu Fibonacciego (n >= 0), aby otrzymać wynik.