import getpass
from garminconnect import Garmin


def main():
    print("Logowanie do Garmin Connect...")
    # Możesz też wpisać tu maile i hasła na sztywno, jeśli wolisz
    email = input("Email: ")
    password = getpass.getpass("Hasło (znaki nie będą widoczne): ")

    try:
        garmin = Garmin(email, password)
        garmin.login()

        # Pobranie tokenów sesji i spakowanie ich do jednego ciągu znaków (JSON)
        token_string = garmin.garth.dumps()

        print("\n" + "=" * 50)
        print("SUKCES! OTO TWÓJ TOKEN SESJI:")
        print("=" * 50 + "\n")
        print(token_string)
        print("\n" + "=" * 50)
        print("Skopiuj cały powyższy ciąg znaków (zaczyna się od klamry {).")

    except Exception as e:
        print(f"Błąd logowania: {e}")


if __name__ == "__main__":
    main()