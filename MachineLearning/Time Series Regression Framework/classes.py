import pandas as pd
import numpy as np

from sklearn import base
from itertools import chain

from collections.abc import Mapping, Sequence, Iterable
from itertools import product
from functools import partial, reduce
import operator


class ToSupervised(base.BaseEstimator, base.TransformerMixin):
	
	def __init__(self, col, groupCol, numLags, dropna=False):
		
		self.col = col
		self.groupCol = groupCol
		self.numLags = numLags
		self.dropna = dropna
	
	def fit(self, X, y=None):
		self.X = X
		return self
	
	def transform(self, X):
		tmp = self.X.copy()
		for i in range(1, self.numLags + 1):
			tmp[str(i) + '_Week_Ago' + "_" + self.col] = tmp.groupby([self.groupCol])[self.col].shift(i)
		
		if self.dropna:
			tmp = tmp.dropna()
			tmp = tmp.reset_index(drop=True)
		
		return tmp


class ToSupervisedDiff(base.BaseEstimator, base.TransformerMixin):
	
	def __init__(self, col, groupCol, numLags, dropna=False):
		
		self.col = col
		self.groupCol = groupCol
		self.numLags = numLags
		self.dropna = dropna
	
	def fit(self, X, y=None):
		self.X = X
		return self
	
	def transform(self, X):
		tmp = self.X.copy()
		for i in range(1, self.numLags + 1):
			tmp[str(i) + '_Week_Ago_Diff_' + "_" + self.col] = tmp.groupby([self.groupCol])[self.col].diff(i)
		
		if self.dropna:
			tmp = tmp.dropna()
			tmp = tmp.reset_index(drop=True)
		
		return tmp


class Kfold_time(object):
	
	def __init__(self, **options):
		
		self.target = options.pop('target', None)
		self.date_col = options.pop('date_col', None)
		self.date_init = options.pop('date_init', None)
		self.date_final = options.pop('date_final', None)
		
		if options:
			raise TypeError("Invalid parameters passed: %s" % str(options))
		
		if ((self.target == None) | (self.date_col == None) | (self.date_init == None) | (self.date_final == None)):
			raise TypeError("Incomplete inputs")
	
	def _train_test_split_time(self, X):
		n_arrays = len(X)
		if n_arrays == 0:
			raise ValueError("At least one array required as input")
		
		for i in range(self.date_init, self.date_final):
			train = X[X[self.date_col] < i]
			val = X[X[self.date_col] == i]
			
			X_train, X_test = train.drop([self.target], axis=1), val.drop([self.target], axis=1)
			y_train, y_test = train[self.target].values, val[self.target].values
			
			yield X_train, X_test, y_train, y_test
	
	def split(self, X):
		cv_t = self._train_test_split_time(X)
		return chain(cv_t)


class BaseEstimator(base.BaseEstimator, base.RegressorMixin):
	def __init__(self, predCol):
		"""
			As a base model we assume the number of sales last week and this week are the same
			Input:
					predCol: l-week ago sales
		"""
		self.predCol = predCol
	
	def fit(self, X, y):
		return self
	
	def predict(self, X):
		prediction = X[self.predCol].values
		return prediction
	
	def score(self, X, y, scoring):
		prediction = self.predict(X)
		
		error = scoring(y, prediction)  # np.sqrt(mean_squared_log_error(y, prediction))
		return error


class TimeSeriesRegressor(base.BaseEstimator, base.RegressorMixin):
	
	def __init__(self, model, cv, scoring, verbosity=True):
		self.model = model
		self.cv = cv
		self.verbosity = verbosity
		self.scoring = scoring
	
	def fit(self, X, y=None):
		return self
	
	def predict(self, X=None):
		
		pred = {}
		for indx, fold in enumerate(self.cv.split(X)):
			X_train, X_test, y_train, y_test = fold
			self.model.fit(X_train, y_train)
			pred[str(indx) + '_fold'] = self.model.predict(X_test)
		
		prediction = pd.DataFrame(pred)
		
		return prediction
	
	def score(self, X, y=None):
		
		errors = []
		for indx, fold in enumerate(self.cv.split(X)):
			
			X_train, X_test, y_train, y_test = fold
			self.model.fit(X_train, y_train)
			prediction = self.model.predict(X_test)
			error = self.scoring(y_test, prediction)
			errors.append(error)
			
			if self.verbosity:
				print("Fold: {}, Error: {:.4f}".format(indx, error))
		
		if self.verbosity:
			print('Total Error {:.4f}'.format(np.mean(errors)))
		
		return errors


class TimeSeriesRegressorLog(base.BaseEstimator, base.RegressorMixin):
	
	def __init__(self, model, cv, scoring, verbosity=True):
		self.model = model
		self.cv = cv
		self.verbosity = verbosity
		self.scoring = scoring
	
	def fit(self, X, y=None):
		return self
	
	def predict(self, X=None):
		
		pred = {}
		for indx, fold in enumerate(self.cv.split(X)):
			X_train, X_test, y_train, y_test = fold
			self.model.fit(X_train, y_train)
			pred[str(indx) + '_fold'] = self.model.predict(X_test)
		
		prediction = pd.DataFrame(pred)
		
		return prediction
	
	def score(self, X, y=None):  # **options):
		
		errors = []
		for indx, fold in enumerate(self.cv.split(X)):
			
			X_train, X_test, y_train, y_test = fold
			self.model.fit(X_train, np.log1p(y_train))
			prediction = np.expm1(self.model.predict(X_test))
			error = self.scoring(y_test, prediction)
			errors.append(error)
			
			if self.verbosity:
				print("Fold: {}, Error: {:.4f}".format(indx, error))
		
		if self.verbosity:
			print('Total Error {:.4f}'.format(np.mean(errors)))
		
		return errors


class TimeGridBasic(base.BaseEstimator, base.RegressorMixin):
	
	def __init__(self, param_grid):
		
		if not isinstance(param_grid, (Mapping, Iterable)):
			raise TypeError('Parameter grid is not a dict or '
			                'a list ({!r})'.format(param_grid))
		
		if isinstance(param_grid, Mapping):
			# wrap dictionary in a singleton list to support either dict
			# or list of dicts
			param_grid = [param_grid]
		
		if isinstance(param_grid, Mapping):
			# wrap dictionary in a singleton list to support either dict
			# or list of dicts
			param_grid = [param_grid]
		
		# check if all entries are dictionaries of lists
		for grid in param_grid:
			if not isinstance(grid, dict):
				raise TypeError('Parameter grid is not a '
				                'dict ({!r})'.format(grid))
			for key in grid:
				if not isinstance(grid[key], Iterable):
					raise TypeError('Parameter grid value is not iterable '
					                '(key={!r}, value={!r})'
					                .format(key, grid[key]))
		
		self.param_grid = param_grid
	
	def __iter__(self):
		"""Iterate over the points in the grid.
		Returns
		-------
		params : iterator over dict of string to any
			Yields dictionaries mapping each estimator parameter to one of its
			allowed values.
		"""
		for p in self.param_grid:
			# Always sort the keys of a dictionary, for reproducibility
			items = sorted(p.items())
			if not items:
				yield {}
			else:
				keys, values = zip(*items)
				for v in product(*values):
					params = dict(zip(keys, v))
					yield params


class TimeSeriesGridSearch(TimeGridBasic, base.BaseEstimator, base.RegressorMixin):
	
	def __init__(self, **options):
		
		self.model = options.pop('model', None)
		self.cv = options.pop('cv', None)
		self.verbosity = options.pop('verbosity', False)
		self.scoring = options.pop('scoring', None)
		param_grid = options.pop('param_grid', None)
		self.param_grid = TimeGridBasic(param_grid)
		
		if options:
			raise TypeError("Invalid parameters passed: %s" % str(options))
		
		if ((self.model == None) | (self.cv == None)):
			raise TypeError("Incomplete inputs")
	
	def fit(self, X, y=None):
		self.X = X
		return self
	
	def _get_score(self, param):
		
		errors = []
		for indx, fold in enumerate(self.cv.split(self.X)):
			
			X_train, X_test, y_train, y_test = fold
			self.model.set_params(**param).fit(X_train, np.log1p(y_train))
			prediction = np.expm1(self.model.predict(X_test))
			error = self.scoring(y_test, prediction)
			errors.append(error)
			
			if self.verbosity:
				print("Fold: {}, Error: {:.4f}".format(indx, error))
		
		if self.verbosity:
			print('Total Error {:.4f}'.format(np.mean(errors)))
		
		return errors
	
	def score(self):
		
		errors = []
		get_param = []
		for param in self.param_grid:
			
			if self.verbosity:
				print(param)
			
			errors.append(np.mean(self._get_score(param)))
			get_param.append(param)
		
		self.sorted_errors, self.sorted_params = (list(t) for t in zip(*sorted(zip(errors, get_param))))
		
		return self.sorted_errors, self.sorted_params
	
	def best_estimator(self, verbosity=False):
		
		if verbosity:
			print('error: {:.4f} \n'.format(self.sorted_errors[0]))
			print('Best params:')
			print(self.sorted_params[0])
		
		return self.sorted_params[0]


