import numpy as np
import pandas as pd
import warnings
from sklearn.exceptions import ConvergenceWarning
warnings.filterwarnings("ignore", category=ConvergenceWarning)
warnings.filterwarnings("ignore", category=UserWarning)

from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel, ConstantKernel as C
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import LeaveOneOut
from sklearn.metrics import r2_score, mean_absolute_error, root_mean_squared_error

class GaussianProcessSurrogate:
    """
    Gaussian Process Surrogate Model for small-sample formulation property prediction.
    Outputs predictive mean mu(x) and predictive epistemic uncertainty sigma(x).
    """
    def __init__(self, kernel=None, random_state=42):
        self.random_state = random_state
        if kernel is None:
            # Matern 5/2 kernel allows smooth modeling of physical response surfaces
            # plus WhiteKernel accounts for experimental wafer-to-wafer measurement noise
            self.kernel = C(1.0, (1e-2, 1e2)) * Matern(length_scale=1.0, length_scale_bounds=(1e-2, 1e2), nu=2.5) + WhiteKernel(noise_level=1e-2, noise_level_bounds=(1e-4, 1.0))
        else:
            self.kernel = kernel
            
        self.scaler = StandardScaler()
        self.model = GaussianProcessRegressor(
            kernel=self.kernel,
            alpha=1e-6,
            normalize_y=True,
            n_restarts_optimizer=10,
            random_state=self.random_state
        )
        self.is_fitted = False
        self.feature_names = None

    def fit(self, X, y, feature_names=None):
        if isinstance(X, pd.DataFrame):
            self.feature_names = X.columns.tolist()
            X_mat = X.values
        else:
            self.feature_names = feature_names
            X_mat = np.array(X)
            
        y_vec = np.array(y)
        X_scaled = self.scaler.fit_transform(X_mat)
        self.model.fit(X_scaled, y_vec)
        self.is_fitted = True
        return self

    def predict(self, X, return_std=True):
        if not self.is_fitted:
            raise RuntimeError("Surrogate model must be fitted before predict() is called.")
        if isinstance(X, pd.DataFrame):
            X_mat = X.values
        else:
            X_mat = np.array(X)
            if X_mat.ndim == 1:
                X_mat = X_mat.reshape(1, -1)
                
        X_scaled = self.scaler.transform(X_mat)
        if return_std:
            mu, std = self.model.predict(X_scaled, return_std=True)
            return mu, std
        else:
            return self.model.predict(X_scaled, return_std=False)

    def evaluate_leave_one_out(self, X, y):
        """
        Runs rigorous Leave-One-Out Cross-Validation (LOOCV) appropriate for N=14.
        """
        if isinstance(X, pd.DataFrame):
            X_mat = X.values
        else:
            X_mat = np.array(X)
        y_vec = np.array(y)

        loo = LeaveOneOut()
        y_true, y_pred = [], []

        for train_idx, test_idx in loo.split(X_mat):
            X_train, X_test = X_mat[train_idx], X_mat[test_idx]
            y_train, y_test = y_vec[train_idx], y_vec[test_idx]

            scaler = StandardScaler()
            X_train_sc = scaler.fit_transform(X_train)
            X_test_sc = scaler.transform(X_test)

            gp = GaussianProcessRegressor(
                kernel=self.kernel,
                alpha=1e-6,
                normalize_y=True,
                n_restarts_optimizer=5,
                random_state=self.random_state
            )
            gp.fit(X_train_sc, y_train)
            pred = gp.predict(X_test_sc)[0]

            y_true.append(y_test[0])
            y_pred.append(pred)

        y_true = np.array(y_true)
        y_pred = np.array(y_pred)

        r2 = r2_score(y_true, y_pred)
        mae = mean_absolute_error(y_true, y_pred)
        rmse = root_mean_squared_error(y_true, y_pred)

        return {
            "r2": float(r2),
            "mae": float(mae),
            "rmse": float(rmse),
            "y_true": y_true,
            "y_pred": y_pred
        }


class DualLithoSurrogate:
    """
    Simultaneously models Line Edge Roughness (LWR) and Sensitivity (Dose).
    """
    def __init__(self):
        self.lwr_model = GaussianProcessSurrogate(random_state=42)
        self.dose_model = GaussianProcessSurrogate(random_state=42)
        self.feature_names = None

    def fit(self, X, y_lwr, y_dose, feature_names=None):
        self.feature_names = X.columns.tolist() if isinstance(X, pd.DataFrame) else feature_names
        self.lwr_model.fit(X, y_lwr, feature_names=self.feature_names)
        self.dose_model.fit(X, y_dose, feature_names=self.feature_names)
        return self

    def predict(self, X):
        mu_lwr, std_lwr = self.lwr_model.predict(X, return_std=True)
        mu_dose, std_dose = self.dose_model.predict(X, return_std=True)
        return {
            "lwr_mean": mu_lwr,
            "lwr_std": std_lwr,
            "dose_mean": mu_dose,
            "dose_std": std_dose
        }


if __name__ == "__main__":
    from dataset import load_ebeam_dataset
    X, y_lwr, y_dose, fnames, df = load_ebeam_dataset()
    print("Testing GaussianProcessSurrogate on LWR...")
    surrogate = GaussianProcessSurrogate()
    surrogate.fit(X, y_lwr)
    
    cv_res = surrogate.evaluate_leave_one_out(X, y_lwr)
    print(f"Leave-One-Out CV Results on LWR (nm):")
    print(f"  R^2 Score: {cv_res['r2']:.3f}")
    print(f"  MAE:       {cv_res['mae']:.3f} nm")
    print(f"  RMSE:      {cv_res['rmse']:.3f} nm")
    
    # Test dual surrogate
    print("\nTesting DualLithoSurrogate...")
    dual = DualLithoSurrogate()
    dual.fit(X, y_lwr, y_dose)
    preds = dual.predict(X.iloc[[0]])
    print(f"Sample Prediction for Ex 1 (Actual: LWR=4.5 nm, Dose=6.0 uC/cm2):")
    print(f"  Predicted LWR:  {preds['lwr_mean'][0]:.2f} +/- {preds['lwr_std'][0]:.2f} nm")
    print(f"  Predicted Dose: {preds['dose_mean'][0]:.2f} +/- {preds['dose_std'][0]:.2f} uC/cm2")
