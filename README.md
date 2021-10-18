# fetch-okta-logs-lambda

Okta の System ログを S3 へ保管するための Lambda 用スクリプト

https://github.com/DefenseStorm/oktaEventLogs を参考にしている。

## Installation

```sh
$ cd fetch-okta-logs-lambda
$ pip install -r requirements.txt -t site-packages
$ cd site-packages
$ zip -r ../function.zip .
$ cd ..
$ zip -g function.zip index.py
$ aws lambda update-function-code --function-name fetch-okta-logs --zip-file fileb://function.zip --publish
```

Report Admin 権限を有したアカウントで API Token を取得する必要がある。
* `管理` > `Security` > `API`

https://developer.okta.com/docs/reference/api/system-log/

Lambda のデプロイ、トークンの取得、後述の環境変数のセットを完了した時点で CloudWatch Events などを使い、Lambda を定期実行（10分に1回程度）する設定を入れる。

### セットする必要のある環境変数

- ORG_URL
  - テナントのURL
- API_TOKEN
  - Report Admin 権限で発行した API トークン
- SEND_BUCKET_NAME
  - 送り先のバケット名
- BUCKET_PREFIX
  - 送り先バケットでのプレフィックス
