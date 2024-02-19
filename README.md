# LaPort

**LaPort**, or LAN portal,
is a simple program to share files and text via local area network.

## Dependencies

- `pyqrcode` (optional) : QR code creation

## Usage

```sh
laport -f path/to/shared_file
```

```sh
laport -d dir/to/store/files
```

```sh
laport -t "Text to send."
echo "Text to send." | laport -t -
```

```sh
laport -p > received_message.txt
```
