enable this example by creating a file "metafile.json"
with the following content (adjust whitelist values):

{
  "name": "smtp_example",
  "smtp": {
    "rule": {
      "singleton": true,
      "target": "smtp_example.smtp.HelloSmtpWorld"
    },
    "whitelist": [
      {
        "ip": "127.0.0.1",
        "system_address": "from@whatever.com"
      }
    ]
  }
}
