# setup
DOCKER_ENV_VARS= \
	--volume="$(PWD):/ws/src/motion":rw

COMMAND="source devel/setup.bash && roslaunch motion bringup.launch"

# === Build docker ===
.PHONY: build
build:
	@echo "Building docker image ..."
	@docker login && docker build -t motion-docker  . 

# === Clean docker ===
.PHONY: clean
clean:
	@echo "Closing all running docker containers ..."
	@docker system prune -f

# === Run terminal docker ===
.PHONY: terminal
terminal:
	@echo "Terminal docker ..."
	@docker run -it --net=host ${DOCKER_ENV_VARS} motion-docker bash

# === setup model ===
.PHONY: setup 
setup:
	@echo "Setup world ..."
	@docker run -it --net=host ${DOCKER_ENV_VARS} motion-docker bash -c ${COMMAND}

# === Start train docker ===
.PHONY: start 
start:
	@echo "Starting training ..."
	@docker run -it --net=host ${DOCKER_ENV_VARS} motion-docker bash -c "source devel/setup.bash && roslaunch motion start.launch"

# === Test Library ===
.PHONY: test-library
test-library:
	@echo "Testing ..."
	@docker run -it --net=host ${DOCKER_ENV_VARS} motion-docker bash -c "source devel/setup.bash && roscd motion && python3 test/library.py"

# === Test ROS ===
.PHONY: test-ros
test-ros:
	@echo "Testing ..."
	@docker run -it --net=host ${DOCKER_ENV_VARS} motion-docker bash -c "source devel/setup.bash && roscd motion && python3 test/ros.py"

# === Test Learning ===
.PHONY: test-learning
test-learning:
	@echo "Testing ..."
	@docker run -it --net=host ${DOCKER_ENV_VARS} motion-docker bash -c "source devel/setup.bash && roscd motion && python3 test/learning.py"

# === Test Full ===
.PHONY: test-full
test-full:
	@echo "Testing ..."
	@docker run -it --net=host ${DOCKER_ENV_VARS} motion-docker bash -c "source devel/setup.bash && roscd motion && python3 test/library.py && python3 test/ros.py"

# === Start Rosboard docker ===
.PHONY: rosboard
rosboard:
	@echo "Starting rosboard ..."
	@echo "Access http://localhost:8888"
	@docker run -it --net=host -p 8888:8888 ${DOCKER_ENV_VARS} motion-docker bash -c "source /opt/ros/noetic/setup.bash && cd src/rosboard && ./run"
