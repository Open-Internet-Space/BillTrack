from decimal import Decimal, ROUND_HALF_UP


def amount_to_words(amount):
    amount = Decimal(amount or 0).quantize(Decimal('0.01'))
    rupees = int(amount)
    paise = int((amount - rupees) * 100)

    ones = [
        '', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
        'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen',
        'Seventeen', 'Eighteen', 'Nineteen'
    ]
    tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']

    def below_hundred(n):
        if n < 20:
            return ones[n]
        return (tens[n // 10] + ' ' + ones[n % 10]).strip()

    def below_thousand(n):
        if n < 100:
            return below_hundred(n)
        return (ones[n // 100] + ' Hundred ' + below_hundred(n % 100)).strip()

    def number_words(n):
        if n == 0:
            return 'Zero'
        parts = []
        for value, label in [(10000000, 'Crore'), (100000, 'Lakh'), (1000, 'Thousand')]:
            if n >= value:
                parts.append(f"{below_thousand(n // value)} {label}")
                n %= value
        if n:
            parts.append(below_thousand(n))
        return ' '.join(part for part in parts if part).strip()

    words = f"Rupees {number_words(rupees)}"
    if paise:
        words += f" and Paise {number_words(paise)}"
    return words + ' Only'


def format_money(amount):
    return f"{Decimal(amount or 0):,.2f}"


def round_rupees(amount):
    return Decimal(amount or 0).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
