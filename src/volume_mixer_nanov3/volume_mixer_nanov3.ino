
const int pot1Pin = A0;
const int pot2Pin = A1;
const int pot3Pin = A2;
const int pot4Pin = A3;

void setup() {
  Serial.begin(115200);
}

void loop() {
  int pot1 = analogRead(pot1Pin);
  int volume1 = map(pot1, 0, 1023, 0, 100);

  int pot2 = analogRead(pot2Pin);
  int volume2 = map(pot2, 0, 1023, 0, 100);

  int pot3 = analogRead(pot3Pin);
  int volume3 = map(pot3, 0, 1023, 0, 100);

  int pot4 = analogRead(pot4Pin);
  int volume4 = map(pot4, 0, 1023, 0, 100);

  Serial.print(volume1);
  Serial.print(",");
  Serial.print(volume2);
  Serial.print(",");
  Serial.print(volume3);
  Serial.print(",");
  Serial.println(volume4);

  delay(50);
}
