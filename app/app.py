from flask import Flask, request, jsonify, render_template, send_from_directory

from blockchain import Blockchain
from uuid import uuid4
import requests
import sys

app = Flask(__name__)
bitcoin = Blockchain()

node_address = str(uuid4()).replace('-', '')


@app.route('/blockchain', methods=['GET']) #전체 블록을 보여줌
def get_blockchain():
    return jsonify(bitcoin.__dict__)

# 블록 체인의 전체 블록을 json 으로 반환한다.


@app.route('/transaction', methods=['POST']) # pending_transactions에 transaction 추가
def create_transaction():
    new_transaction = request.get_json()
    block_index = bitcoin.add_transaction_to_pending_transactions(new_transaction)
    return jsonify({'note': f'Transaction will be added in block {block_index}.'})

# json 으로 새로운 트랜잭션을 받는다.
# 새로운 트랜잭션을 pending_transactions에 추가한다.
# 해당 트랜잭션이 추가될 블록의 인덱스를 json 으로 반환한다.


@app.route('/mine', methods=['GET']) # 작업증명
def mine():
    last_block = bitcoin.get_last_block()
    previous_block_hash = last_block['hash']
    current_block_data = {
        'transactions': bitcoin.pending_transactions,
        'index': last_block['index'] + 1
    }
    bitcoin.create_new_transaction(12.5, "00", node_address)
    nonce = bitcoin.proof_of_work(previous_block_hash, current_block_data)
    block_hash = bitcoin.hash_block(previous_block_hash, current_block_data, nonce)
    new_block = bitcoin.create_new_block(nonce, previous_block_hash, block_hash)

    request_promises = []

    for network_node_url in bitcoin.network_nodes:
        request_options = {
            'newBlock': new_block
        }
        res = requests.post(network_node_url + '/receive-new-block', json=request_options)
        request_promises.append(res)

    responses = [rp.json() for rp in request_promises]

    request_options = {
        'amount': 12.5,
        'sender': "00",
        'recipient': node_address
    }

    requests.post(bitcoin.current_node_url + '/transaction/broadcast', json=request_options)

    return jsonify({
        'note': "New block mined successfully",
        'block': new_block
    })

# 작업 증명
# last_block에 마지막 블록을 가져온다.
# previous_block_hash에 이전 블록의 해시 값을 저장한다.
# current_block_data에 현재 블록의 데이터를 대기 중인 트랜잭션 목록과 마지막 블록의 인덱스에 1을 더한 값을 저장한다.
# 12.5 비트코인을 보상으로 수신하는 새로운 트랜잭션을 생성한다.
# nonce에 작업 증명을 수행하여 nonce 값 찾기.
# block_hash에 이전 블록의 해시 값, 현재 블록 데이터, nonce 값을 사용하여 블록의 해시 값을 계산.
# new_block에 nonce, 이전 블록의 해시 값, 블록 해시 값을 사용하여 새로운 블록을 생성.

# 모든 노드에게 브로드캐스트 기능
# request_promises 리스트를 초기화.
# 블록체인 네트워크의 각 노드에 대해 POST로 생성된 블럭을 JSON으로 전송. 전송한건 request_promises 리스트에 추가.
# request_promises의 응답들을 responses 리스트에 저장
# 새로운 블록의 채굴 보상을 수신하기 위해 블록체인 네트워크의 각 노드에 대해 트랜잭션을 POST로 보상 트랜잭션의 정보를 브로드캐스트.
# json 으로 생성된 블럭 응답 반환


@app.route('/register-and-broadcast-node', methods=['POST'])
def register_and_broadcast_node():
    new_node_url = request.json['newNodeUrl']

    if new_node_url not in bitcoin.network_nodes:
        bitcoin.network_nodes.append(new_node_url)

    reg_nodes_promises = []
    for network_node_url in bitcoin.network_nodes:
        response = requests.post(f"{network_node_url}/register-node", json={'newNodeUrl': new_node_url}) # 새로운 노드를 연결하는 요청 받은 노드가 원래 연결되어 있던 노드에게 새로운 노드를 등록하는 요청 보내는 API 호출
        reg_nodes_promises.append(response)

    for response in reg_nodes_promises:
        if response.status_code == 200:
            requests.post(f"{new_node_url}/register-nodes-bulk", json={'allNetworkNodes': bitcoin.network_nodes + [bitcoin.current_node_url]}) # 새로운 노드를 추가한 뒤 전체 노드 정보를 새로 연결되는 노드에게 주는 API 호출

    return jsonify({'note': 'New node registered with network successfully.'})

# 새로운 노드를 추가하고 네트워크에 브로드캐스트하는 역할
# 요청에서 new_node_url를 저장.
# bitcoin.network_nodes에 new_node_url이 없는 경우, 새로운 노드를 bitcoin.network_nodes에 추가.
# reg_nodes_promises 리스트를 초기화.

# 모든 노드를 순회하면서 새로운 노드의 정보를 전달
# bitcoin.network_nodes에 있는 각 네트워크 노드에 대해 새로운 노드를 등록하는 POST 요청을 newNodeUrl을 담아서 보내기.
# 전송된 요청은 reg_nodes_promises 리스트에 추가.

# status_code가 200(정상)이면 network_nodes와 현재 node 즉, 모든 node를 전달
# reg_nodes_promises에 있는 각 응답을 확인하여 상태 코드가 200인 경우, 새로운 노드에게 bitcoin.network_nodes와 현재 노드 URL을 포함한 전체 네트워크 노드 정보를 전송하는 POST 요청을 보냅니다.
# 성공했다는 응답 json 으로 반환


@app.route('/register-node', methods=['POST']) # 새로운 노드를 연결하는 요청 받은 노드가 원래 연결되어 있던 노드에게 새로운 노드를 등록하는 요청 보내는 API
def register_node():
    new_node_url = request.json['newNodeUrl']
    node_not_already_present = new_node_url not in bitcoin.network_nodes #채우시오 : new_node_url이 network_noeds에 없으면 true (type boolean)
    not_current_node = bitcoin.current_node_url != new_node_url#채우시오 : current_node_url이 new_node_url이 아니면 true(type boolean)
    if node_not_already_present and not_current_node:#두 가지 조건을 모두 만족하면 실행
        bitcoin.network_nodes.append(new_node_url) #새로운 노드 network_node에 추가

    return jsonify({'note': 'New node registered successfully.'})

# 현재 연결중인 node에게 새로운 node의 정보 전달
# 현재 연결중인 node가 아니라는 조건문 작성
# Chain 구조상 현재 노드는 network node에 포함 되어있지 않음. 따라서 현재 노드가 newnode가 아니라는 조건문 작성

# 노드 추가 요청받은 노드가 연결되어 있던 노드에게 등록 요청하는 API
# 새로운 노드를 등록
# 요청에서 'newNodeUrl'을 가져와 저장.
# new_node_url이 network_nodes에 없으면 true
# current_node_url이 new_node_url이 아니면 true
# 새로운 노드가 네트워크에 있고 bitcoin.current_node_url 와 같다면 새로운 노드를 network_nodes에 추가
# 성공 응답을 json으로 반환


@app.route('/register-nodes-bulk', methods=['POST']) # 새로운 노드를 추가한 뒤 전체 노드 정보를 새로 연결되는 노드에게 주는 API
def register_nodes_bulk():
    all_network_nodes = request.json['allNetworkNodes']
    for network_node_url in all_network_nodes:
        node_not_already_present = network_node_url not in bitcoin.network_nodes #채우시오 : new_node_url이 network_noeds에 없으면 true (type boolean)
        not_current_node = bitcoin.current_node_url != network_node_url #채우시오 : current_node_url이 new_node_url이 아니면 true(type boolean)
        if node_not_already_present and not_current_node: #두 가지 조건을 모두 만족하면 실행
            bitcoin.network_nodes.append(network_node_url) #새로운 노드 network_node에 추가

    return jsonify({'note': 'Bulk registration successful.'})

# 현재 연결중인 node에게 새로운 node의 정보 전달
# 현재 연결중인 node가 아니라는 조건문 작성
# Chain 구조상 현재 노드는 network node에 포함 되어있지 않음. 따라서 현재 노드가 newnode가 아니라는 조건문 작성

# 연결된 전체 노드의 정보를 새로 추가된 노드에게 전달
# 요청에서 all_network_nodes를 저장.
# all_network_nodes의 모든 노드 반복
# new_node_url이 network_noeds에 없으면 true
# current_node_url이 new_node_url이 아니면 true
# 새로운 노드가 네트워크에 있고 bitcoin.current_node_url 와 같다면 새로운 노드를 network_nodes에 추가
# 성공 응답 json으로 반환.



@app.route('/transaction/broadcast', methods=['POST'])
def broadcast_transaction():
    new_transaction = bitcoin.create_new_transaction(
        request.json['amount'],
        request.json['sender'],
        request.json['recipient']
    )
    bitcoin.add_transaction_to_pending_transactions(new_transaction)

    request_promises = []
    for network_node_url in bitcoin.network_nodes:
        request_options = {
            'url': network_node_url + '/transaction',
            'json': new_transaction
        }
        request_promises.append(requests.post(**request_options))

    for response in request_promises:
        response.raise_for_status()

    return jsonify({'note': 'Transaction created and broadcast successfully.'})

# Request.json 함수를 이용하여 금액, 발신자, 수신자 저장 후 tx 생성
# 모든 newwork_node에 tx 생성 반복문 작성

# 트랜잭션을 생성하고 네트워크 노드에 브로드캐스트하는 역할을 합니다.
# 요청에서 'amount', 'sender', 'recipient'를 가져와 새로운 트랜잭션인 new_transaction을 생성합니다.
# new_transaction을 bitcoin.add_transaction_to_pending_transactions 메서드를 사용하여 대기 중인 트랜잭션에 추가합니다.
# request_promises라는 빈 리스트를 생성합니다.
# bitcoin.network_nodes에 포함된 각각의 network_node_url에 대해 반복합니다.
# 각 network_node_url에 대한 POST 요청을 보내기 위한 request_options를 생성합니다.
# 'url'은 network_node_url + '/transaction'으로 설정됩니다.
# 'json'은 new_transaction으로 설정됩니다.
# requests.post를 사용하여 POST 요청을 보내고, 반환된 응답을 request_promises 리스트에 추가합니다.
# request_promises에 저장된 각각의 응답에 대해 상태 코드를 확인합니다.
# 응답의 상태 코드가 정상적이지 않으면 예외를 발생시킵니다.
# JSON 형식으로 응답을 생성하여 "Transaction created and broadcast successfully."와 함께 응답을 반환합니다.


@app.route('/receive-new-block', methods=['POST'])
def receive_new_block():
    new_block = request.json['newBlock']
    last_block = bitcoin.get_last_block()
    correct_hash = last_block['hash'] == new_block['previous_block_hash']
    correct_index = last_block['index'] + 1 == new_block['index']

    if correct_hash and correct_index:
        bitcoin.chain.append(new_block)
        bitcoin.pending_transactions = []
        return jsonify({
            'note': 'New block received and accepted',
            'newBlock': new_block
        })
    else:
        return jsonify({
            'note': 'New block rejected.',
            'newBlock': new_block
        })


# Correct_hash : 전 블록 해쉬값과 new 블록 previous_block_hash 값 비교
# Correct_index : 전 블록 인덱스값 + 1과 new 블록 index 값이 같은지 비교
# 이후 new block을 chain의 추가 후 p_transaction 초기화

# 함수는 새로운 블록을 받아들이고 체인에 추가하는 역할을 합니다.
# 요청에서 new_block을 가져오고 블록체인의 마지막 블록을 가져와 .
# 현재 블록의 이전 블록 해시값과 새로운 블록의 'previous_block_hash'가 일치하는지 확인.
# 현재 블록의 인덱스에 1을 더한 값이 새로운 블록의 'index'와 일치하는지 확인.
# correct_hash와 correct_index가 모두 참이면, 새로운 블록은 유효한 블럭이므로 새 블럭을 블록체인에 추가하고 pending_transactions 초기화후 새로운 블럭 응답으로 반환.
# correct_hash 또는 correct_index가 거짓인 경우, 새로운 블럭이 유효한 블럭이 아니므로 새로운 블럭은 거부되었다고 응답 반환.



if __name__ == "__main__":
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    else:
        port = 5000  # 기본 포트 번호를 설정하십시오.

    if len(sys.argv) > 2:
        current_node_url = sys.argv[2]
    else:
        current_node_url = f"http://localhost:{port}"

    bitcoin = Blockchain(current_node_url)  # 현재 노드 URL 전달
    app.run(host="0.0.0.0", port=port)