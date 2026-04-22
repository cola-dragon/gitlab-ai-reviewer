# Security Policy / 安全策略

## Supported use / 支持范围

This project is provided as an open-source tool and reference implementation.  
It is intended for self-hosted deployment and further customization.

本项目作为开源工具和参考实现提供，主要面向自部署和二次开发场景。

At the current stage, security hardening should be treated as a deployment responsibility shared by maintainers and operators.

在当前阶段，安全加固应视为维护者与部署者共同承担的工作。

---

## Reporting a vulnerability / 漏洞报告方式

Please avoid filing a public issue for vulnerabilities that could expose users or deployments.

对于可能影响用户或部署安全的漏洞，请避免直接公开提 issue。

Instead, please report with:

- affected version or commit
- reproduction steps
- impact summary
- suggested mitigation if available

建议在反馈中提供：

- 受影响版本或 commit
- 复现步骤
- 影响说明
- 如有可能，给出缓解建议

If you do not have a private reporting channel yet, create one before publishing the repository broadly. Until then, avoid disclosing exploit details publicly.

如果你当前还没有私密安全反馈渠道，建议在正式大范围公开仓库前先建立一个。建立之前，请避免公开披露可直接利用的细节。

---

## Security guidance for operators / 给部署者的安全建议

If you run this project in your own environment, you should:

- use a dedicated bot account
- scope GitLab tokens as narrowly as practical
- store secrets only in environment variables or a secret manager
- protect the webhook endpoint behind trusted network boundaries
- rotate keys if they are exposed
- review logs before sharing them externally

如果你要自行部署，建议：

- 使用专用 bot 账号
- 尽量收窄 GitLab token 的权限范围
- 仅通过环境变量或密钥管理服务保存密钥
- 将 webhook 接口放在受信网络边界之后
- 如果密钥暴露，立即轮换
- 对外共享日志前先做脱敏

---

## Out of scope / 非漏洞范围

The following are generally out of scope unless they clearly lead to a real exploit path:

- requests for broader product features
- theoretical issues without a realistic attack path
- environment-specific misconfiguration outside the project defaults

以下内容通常不作为漏洞处理，除非能证明存在实际利用路径：

- 更广泛的产品功能需求
- 没有现实攻击路径的理论性问题
- 超出项目默认行为的环境专属配置错误
