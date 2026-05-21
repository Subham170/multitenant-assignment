from kfp import dsl
from kfp import compiler

@dsl.component(
    base_image="python:3.10",
    packages_to_install=["pandas", "scikit-learn"],
)
def train_model():

    import pandas as pd
    from sklearn.datasets import load_iris
    from sklearn.linear_model import LogisticRegression

    iris = load_iris()

    X = iris.data
    y = iris.target

    model = LogisticRegression(max_iter=200)

    model.fit(X, y)

    # Predict on different iris rows (setosa, versicolor, virginica regions)
    samples = [0, 50, 100]
    print("RCB Pipeline Running...")
    for i in samples:
        pred = model.predict([X[i]])[0]
        actual = y[i]
        print(f"  sample {i}: predicted={pred}, actual={actual}")

@dsl.pipeline(
    name="rcb-ml-pipeline"
)
def rcb_pipeline():

    train_model()

if __name__ == "__main__":

    compiler.Compiler().compile(
        rcb_pipeline,
        "pipelines/rcb_pipeline.yaml"
    )