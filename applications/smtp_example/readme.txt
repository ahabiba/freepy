enable this example by creating a file "metafile.json"
with the following content (adjust whitelist values):

{
  "name": "smtp_example",
  "smtp": {
    "rule": {
      "singleton": true,
      "target": "smtp_example.hello_smtp_world.HelloSmtpWorld"
    },
    "whitelist": {
      "allow_all": true,
      "ips": [
        "127.0.0.1"
      ]
    }
  }
}
