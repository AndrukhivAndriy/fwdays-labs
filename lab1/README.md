# Module 02 — Security & Policy as Code

**Звіт про виконання лабораторної роботи**  
**Середовище:** Kubernetes k3s на AWS EC2  
**Helm chart:** `fwdays-lab`  
**Helm release:** `learning-lab` (`default`)

## Завдання 1. Kubernetes, окремі kubeconfig та RBAC

**Вимога:** створити namespace ментора та трьох студентів, окремі kubeconfig, налаштувати RW/RO доступи без Cluster Admin.

### 1.1. Створено чотири namespaces — виконано ✅

Команда:

```bash
kubectl get namespaces -L person-role
```

Фактичний результат:

```text
NAME              STATUS   AGE     PERSON-ROLE
default           Active   14d
kube-node-lease   Active   14d
kube-public       Active   14d
kube-system       Active   14d
kyverno           Active   5m57s
mentor            Active   22h     mentor
student01         Active   22h     student
student02         Active   22h     student
student03         Active   22h     student
```

**Підтвердження:** `mentor`, `student01`, `student02`, `student03` мають статус `Active`. Шаблон `templates/namespaces.yaml` формує namespaces на основі `values.yaml`.

### 1.2. Згенеровано окремі kubeconfig — виконано ✅

ServiceAccount створюються Helm-шаблоном `templates/serviceaccount.yaml`. Скрипт `kubeconfig-generator.py` бере користувачів із `values.yaml` без фіксованого списку, генерує окремі kubeconfig на основі токенів ServiceAccount.

Команда запуску:

```bash
python kubeconfig-generator.py
```

Фактичний результат:

```text
Users: 4

[OK] mentor/mentor -> mentor.kubeconfig
[OK] student01/student01 -> student01.kubeconfig
[OK] student02/student02 -> student02.kubeconfig
[OK] student03/student03 -> student03.kubeconfig

Generated: 4/4
```

**Підтвердження:** успішно згенеровано 4 із 4 файлів. Токени мають обмежений строк дії; для перевипуску запускається той самий скрипт.

### 1.3. Призначено права RBAC — виконано в конфігурації ✅

Helm-шаблони `templates/clusteroles.yaml`, `templates/student-rolebinding.yaml` та `templates/mentor-rolebinding.yaml` створюють ролі й прив'язки. `ClusterRole/lab-rw` дозволяє читання і зміну визначених namespaced ресурсів, `ClusterRole/lab-ro` — тільки читання. Доступ надається через `RoleBinding` у конкретному namespace.

| Ідентичність | Namespace | Права |
|---|---|---|
| `mentor` | `mentor` | RW |
| `mentor` | `student01`, `student02`, `student03` | RW |
| `student01` | `student01` | RW |
| `student02` | `student01`, `default` | RO |
| `student03` | `student03` | RW |

Фактично отримані RoleBinding:

```text
# mentor
mentor-own-rw   ClusterRole/lab-rw

# student01
mentor-rw       ClusterRole/lab-rw
student01-rw    ClusterRole/lab-rw
student02-ro    ClusterRole/lab-ro

# student02
mentor-rw       ClusterRole/lab-rw

# student03
mentor-rw       ClusterRole/lab-rw
student03-rw    ClusterRole/lab-rw

# default
student02-ro    ClusterRole/lab-ro
```

Підтверджено, що `student02-ro` посилається на ServiceAccount:

```bash
kubectl get rolebinding student02-ro -n student01 -o jsonpath='{.subjects}{"\n"}'
```

```json
[{"kind":"ServiceAccount","name":"student02","namespace":"student02"}]
```

### 1.4. RO-доступ студента 02 — перевірено на кластері ✅

Команда:

```bash
for ns in student01 default; do for verb in get create; do printf 'student02 | %s | %s: ' "$ns" "$verb"; kubectl auth can-i "$verb" pods -n "$ns" --as=system:serviceaccount:student02:student02; done; done
```

Фактичний результат:

```text
student02 | student01 | get: yes
student02 | student01 | create: no
student02 | default | get: yes
student02 | default | create: no
```

**Підтвердження:** `student02` може читати Pod у `student01` і `default`, але не може їх створювати.

**Підсумок завдання 1:** namespaces, окремі kubeconfig та RBAC створено; RO-доступ `student02` підтверджено тестом. Перевірку відсутності Cluster Admin для всіх користувачів ще потрібно задокументувати фактичним виводом.

## Завдання 2. Kyverno: read-only root filesystem у режимі Audit

**Вимога:** перевіряти `securityContext.readOnlyRootFilesystem: true`, реєструвати порушення, не блокуючи Pod.

### 2.1. Kyverno встановлено — виконано ✅

Команда:

```bash
kubectl get pods -n kyverno
```

Фактичний результат:

```text
NAME                                            READY   STATUS    RESTARTS
kyverno-admission-controller-75bb8dfc78-72lr5   1/1     Running   0
kyverno-background-controller-9fdc784fb-4pltf   1/1     Running   0
kyverno-cleanup-controller-6484bbdd59-77pd8     1/1     Running   0
kyverno-reports-controller-c69bfbdc6-96cxl      1/1     Running   0
```

### 2.2. Audit-політика активна — виконано ✅

Файл `templates/kyverno-validation.yaml` створює `ClusterPolicy/lab-require-readonly-rootfs` із `validate.failureAction: Audit`. Політика перевіряє контейнери та наявні initContainers у namespaces з `person-role=student` або `person-role=mentor`.

Команда:

```bash
kubectl get clusterpolicies
```

Фактичний результат:

```text
NAME                          ADMISSION   BACKGROUND   READY   MESSAGE
lab-add-person-label          true        false        True    Ready
lab-require-readonly-rootfs   true        true         True    Ready
```

### 2.3. Audit протестовано — виконано ✅

Команди:

```bash
kubectl run kyverno-test --image=nginx:alpine -n student01
kubectl run kyverno-test --image=nginx:alpine -n mentor
```

Фактичний результат:

```text
pod/kyverno-test created
pod/kyverno-test created
```

Команда:

```bash
kubectl get policyreports -A
```

Фактичний результат:

```text
NAMESPACE   KIND   NAME           PASS   FAIL   WARN   ERROR   SKIP
mentor      Pod    kyverno-test   1      1      0      0       0
student01   Pod    kyverno-test   1      1      0      0       0
```

**Підтвердження:** Pod створилися, а PolicyReport зафіксував порушення (`FAIL=1`) у кожному namespace. Точну назву правила в `FAIL` у наданому виводі не показано, але це узгоджується з налаштованою Audit-політикою.

**Підсумок завдання 2: виконано та протестовано.**

## Завдання 3. Kyverno: автоматична мітка `person`

**Вимога:** `person=student` у студентських namespaces, `person=mentor` у namespace ментора, відсутність `person` в усіх інших namespaces.

### 3.1. Мітка `person=student` — виконано та протестовано ✅

Файл `templates/kyverno-mutation.yaml` створює `ClusterPolicy/lab-add-person-label`, яка вибирає namespaces за `person-role=student`.

Команда:

```bash
kubectl get pod kyverno-test -n student01 -o jsonpath='{.metadata.labels.person}{"\n"}'
```

Фактичний результат:

```text
student
```

### 3.2. Мітка `person=mentor` — виконано та протестовано ✅

Та сама політика вибирає namespace за `person-role=mentor`.

Команда:

```bash
kubectl get pod kyverno-test -n mentor -o jsonpath='{.metadata.labels.person}{"\n"}'
```

Фактичний результат:

```text
mentor
```
