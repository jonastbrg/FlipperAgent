---
name: credential-test
description: "Test default credentials against network services — SSH, HTTP, FTP, Telnet, MQTT, MySQL, PostgreSQL, Redis, MongoDB"
---

# Credential Testing

Test common default credentials against network services using native CLI tools. HIGH risk -- active authentication attempts against live services.

## Rate limiting

- Wait at least **0.5 seconds** between attempts per target to avoid account lockouts.
- Limit concurrent checks to **3 max**.
- Cap total attempts at **50 pairs** per spray operation.

## Default ports

| Service | Default Port |
|---------|-------------|
| SSH | 22 |
| HTTP | 80 |
| FTP | 21 |
| Telnet | 23 |
| MQTT | 1883 |
| MySQL | 3306 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| MongoDB | 27017 |

## Testing commands by service

### SSH

Requires `sshpass` for password auth (`brew install hudochenkov/sshpass/sshpass`).

```bash
sshpass -p 'PASSWORD' ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -p 22 USER@TARGET echo AUTH_OK
```

Exit code 0 = success. For empty-password/key-based auth, use `BatchMode=yes` instead of sshpass.

### HTTP basic auth

```bash
curl -s -o /dev/null -w '%{http_code}' -u USER:PASSWORD http://TARGET:80/
```

Status 401 = bad creds. Any other status (200, 301, 302, 403) may indicate valid creds.
For HTTPS on port 443 or 8443, use `https://` and add `-k` to skip cert verification.

### FTP

```bash
curl -s --connect-timeout 3 --max-time 5 -u USER:PASSWORD ftp://TARGET:21/
```

For anonymous: `curl -s ftp://TARGET:21/` or `-u anonymous:`.

### Telnet

Telnet auth testing requires expect-style interaction. For basic port-open check only:

```bash
python3 -c "
import socket
s = socket.socket()
s.settimeout(3)
try:
    s.connect(('TARGET', 23))
    print('Telnet port open')
    s.close()
except:
    print('Telnet port closed')
"
```

### MQTT

Requires `mosquitto_pub` (`brew install mosquitto`).

```bash
mosquitto_pub -h TARGET -p 1883 -t test/auth -m ping -u USER -P PASSWORD
```

Exit code 0 = auth succeeded.

### MySQL

```bash
mysql --host=TARGET --port=3306 --user=USER --password=PASSWORD --connect-timeout=3 -e "SELECT 1;"
```

### PostgreSQL

```bash
PGPASSWORD=PASSWORD psql --host=TARGET --port=5432 --username=USER --no-password -c "SELECT 1;"
```

### Redis

```bash
redis-cli -h TARGET -p 6379 -a PASSWORD PING
```

Expect `PONG` in output for success. For no-auth: `redis-cli -h TARGET -p 6379 PING`.

### MongoDB

```bash
mongosh --quiet --eval "db.runCommand({ping:1})" "mongodb://USER:PASSWORD@TARGET:27017/"
```

For no-auth: `mongodb://TARGET:27017/`.

## Default credentials database

### SSH (20 pairs)
| Username | Password |
|----------|----------|
| root | root |
| admin | admin |
| root | toor |
| pi | raspberry |
| root | password |
| ubuntu | ubuntu |
| user | user |
| test | test |
| root | alpine |
| root | *(empty)* |
| admin | password |
| admin | 1234 |
| root | 12345 |
| root | changeme |
| deploy | deploy |
| vagrant | vagrant |
| ec2-user | *(empty)* |
| centos | centos |
| oracle | oracle |
| guest | guest |

### HTTP (20 pairs)
| Username | Password |
|----------|----------|
| admin | admin |
| admin | password |
| admin | 1234 |
| root | root |
| admin | *(empty)* |
| admin | 12345 |
| admin | changeme |
| administrator | administrator |
| user | user |
| test | test |
| admin | admin123 |
| root | password |
| admin | pass |
| admin | secret |
| webadmin | webadmin |
| tomcat | tomcat |
| manager | manager |
| admin | default |
| cisco | cisco |
| admin | admin1234 |

### FTP (20 pairs)
| Username | Password |
|----------|----------|
| anonymous | *(empty)* |
| ftp | ftp |
| admin | admin |
| root | root |
| user | user |
| anonymous | anonymous@ |
| admin | password |
| test | test |
| ftpuser | ftpuser |
| admin | 1234 |
| ftp | password |
| guest | guest |
| admin | *(empty)* |
| root | password |
| backup | backup |
| operator | operator |
| admin | admin123 |
| www | www |
| web | web |
| upload | upload |

### Telnet (20 pairs)
| Username | Password |
|----------|----------|
| root | root |
| admin | admin |
| root | *(empty)* |
| admin | password |
| admin | 1234 |
| user | user |
| root | password |
| admin | *(empty)* |
| enable | *(empty)* |
| guest | guest |
| root | default |
| admin | admin123 |
| supervisor | supervisor |
| tech | tech |
| support | support |
| root | toor |
| root | 12345 |
| admin | changeme |
| manager | manager |
| cisco | cisco |

### MQTT (20 pairs)
| Username | Password |
|----------|----------|
| *(empty)* | *(empty)* |
| admin | admin |
| mqtt | mqtt |
| user | password |
| admin | password |
| guest | guest |
| test | test |
| iot | iot |
| mosquitto | mosquitto |
| admin | public |
| admin | *(empty)* |
| root | root |
| client | client |
| device | device |
| sensor | sensor |
| admin | broker |
| mqtt_user | mqtt_pass |
| homeassistant | homeassistant |
| openhab | openhab |
| admin | hivemq |

### MySQL (20 pairs)
| Username | Password |
|----------|----------|
| root | *(empty)* |
| root | root |
| root | mysql |
| root | password |
| root | toor |
| admin | admin |
| mysql | mysql |
| root | 123456 |
| root | 12345 |
| root | changeme |
| dba | dba |
| dbadmin | dbadmin |
| root | master |
| root | default |
| test | test |
| root | admin |
| user | user |
| root | 1234 |
| mysqladmin | mysqladmin |
| root | maria |

### PostgreSQL (20 pairs)
| Username | Password |
|----------|----------|
| postgres | postgres |
| postgres | *(empty)* |
| postgres | password |
| admin | admin |
| postgres | admin |
| postgres | root |
| postgres | 123456 |
| postgres | changeme |
| pgsql | pgsql |
| postgres | pg |
| dbuser | dbuser |
| postgres | default |
| test | test |
| user | user |
| postgres | 1234 |
| postgres | master |
| postgres | pgsql |
| pgadmin | pgadmin |
| replication | replication |
| postgres | letmein |

### Redis (20 pairs)
| Username | Password |
|----------|----------|
| *(empty)* | *(empty)* |
| *(empty)* | redis |
| *(empty)* | password |
| *(empty)* | foobared |
| *(empty)* | admin |
| *(empty)* | root |
| *(empty)* | 123456 |
| *(empty)* | default |
| *(empty)* | changeme |
| *(empty)* | letmein |
| default | *(empty)* |
| default | redis |
| admin | admin |
| redis | redis |
| *(empty)* | 1234 |
| *(empty)* | test |
| *(empty)* | secret |
| *(empty)* | master |
| *(empty)* | pass |
| *(empty)* | redis123 |

### MongoDB (20 pairs)
| Username | Password |
|----------|----------|
| *(empty)* | *(empty)* |
| admin | admin |
| root | root |
| admin | password |
| admin | *(empty)* |
| mongo | mongo |
| admin | 123456 |
| admin | changeme |
| root | password |
| admin | admin123 |
| mongouser | mongopass |
| admin | mongo |
| root | *(empty)* |
| dbadmin | dbadmin |
| test | test |
| user | user |
| admin | default |
| admin | 1234 |
| root | mongo |
| admin | secret |

## Notes

- Credential testing is HIGH risk -- active authentication against live services.
- Always get explicit authorization before testing credentials.
- Rate-limit attempts (0.5s minimum delay) to avoid triggering lockouts.
- Finding valid default credentials is a CRITICAL security finding.
- For automated batch testing, loop through the credential pairs above with appropriate delays.
- `sshpass` is required for SSH password testing; install if not present.
