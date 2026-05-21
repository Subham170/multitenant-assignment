from kfp import dsl
from kfp import compiler

@dsl.component(
    base_image="python:3.10",
    packages_to_install=["scikit-learn"],
)
def train_model():
    from sklearn.datasets import load_wine
    from sklearn.tree import DecisionTreeClassifier

    wine = load_wine()
    X = wine.data
    y = wine.target

    model = DecisionTreeClassifier(max_depth=3, random_state=42)
    model.fit(X, y)

    # Predict on different wine rows to show varied class labels
    samples = [0, 50, 100]
    print("RR Pipeline")
    for i in samples:
        pred = int(model.predict([X[i]])[0])
        actual = int(y[i])
        print(f"  sample {i}: predicted={pred}, actual={actual}")

@dsl.pipeline(name="rr-pipeline")
def rr_pipeline():
    train_model()

if __name__ == "__main__":
    compiler.Compiler().compile(rr_pipeline, "pipelines/rr_pipeline.yaml")
