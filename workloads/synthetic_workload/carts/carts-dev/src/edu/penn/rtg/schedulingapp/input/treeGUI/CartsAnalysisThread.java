package edu.penn.rtg.schedulingapp.input.treeGUI;

import javax.swing.JOptionPane;

import edu.penn.rtg.common.GlobalVariable;
import edu.penn.rtg.schedulingapp.input.treeGUI.translator.SchedulingTreeRoot2ComponentRoot;
import edu.penn.rtg.schedulingapp.output.OutputI;
import edu.penn.rtg.schedulingapp.output.graph.GenGraph;
import edu.penn.rtg.schedulingapp.*;

public class CartsAnalysisThread extends Thread{
	String algo;
	TreeComponent root;
	TreeComponent comp;
	OutputI output;
	CartsTree cartsTree;
	boolean isCompute;
	public CartsAnalysisThread(TreeComponent comp) {
		super();
		this.comp = comp;
		isCompute=false;
	}
	public CartsAnalysisThread(String algo, TreeComponent comp,TreeComponent root,
			OutputI output, CartsTree cartsTree) {
		super();
		this.algo = algo;
		this.comp = comp;
		this.root =root;
		this.output = output;
		this.cartsTree = cartsTree;
		isCompute=true;
	}
	
	public void run()
	{
		try {
			if (isCompute) {
				if (algo.equalsIgnoreCase("PRM")
						|| algo.equalsIgnoreCase("EDP")
						|| algo.equalsIgnoreCase("EQV")
						|| algo.equalsIgnoreCase("SIRAP")) {
					compute();
				} else {
					compute2();
				}

			} else {
				draw();
			}
		} catch (Exception e) {
			e.printStackTrace();
		}
		
	}
	
	private void draw() throws Exception {
		GenGraph.drawGraph(comp);
	}
	
	private void compute() throws Exception {
		comp.getSchCom().setRevised(false);
		String str = Analysis.preProcess(algo,comp);
		if(comp.getSchCom().isRevised()) {
			if(!comp.isProcessed()) {
				root.setProcessedRecursive(false);
				output.displayEmpty();
				cartsTree.updateUI();
				return;
			}
			root.setProcessedRecursive(false);
			comp.setProcessedRecursive(true);
			output.displayOutput(comp, str);
			cartsTree.updateUI();
		}
	}
	
	private void compute2() throws Exception {
		String algo = this.algo;
		comp.getSchCom().setRevised(false);
		
		//String str = Analysis.preProcess(algo,comp);
		if(algo.equalsIgnoreCase("MPR") || algo.equalsIgnoreCase("MPR2") || algo.equalsIgnoreCase("MPR2_Meng") || algo.equalsIgnoreCase("MPR_Meng")){
			System.out.println("compute2(): MPR or MPR2_Meng");
			int sbf_type = -1;
			if(algo.equalsIgnoreCase("MPR") || algo.equalsIgnoreCase("MPR2") ){
				sbf_type = GlobalVariable.MPR_SBF_ARVIND;
			}else if( algo.equalsIgnoreCase("MPR2_Meng") || algo.equalsIgnoreCase("MPR_Meng") ){
				sbf_type = GlobalVariable.MPR_SBF_MENG;
			}else{
				System.err.println("No such analysis model! only support MPR/MPR2/MPR2_Meng/MPR_Meng. Exit(1)\n");
				System.exit(1);
			}
			edu.penn.rtg.csa.mpr2.Component comp_mpr2 = SchedulingTreeRoot2ComponentRoot.transfer2MPR2Root(comp,null);
			String result_mpr= edu.penn.rtg.csa.mpr2.MPR2Analysis.
						doCSA_start(comp_mpr2, GlobalVariable.ARVIND_SCHEDTEST_FAST, sbf_type);
			if(!result_mpr.contains("SUCCESS")){
				JOptionPane.showMessageDialog(null,result_mpr,"ERROR!",JOptionPane.ERROR_MESSAGE);
				return;
			}
			SchedulingTreeRoot2ComponentRoot.transfer2TreeComponent(comp_mpr2, this.comp);
			comp.setResourceModel("MPR");
			
		}
		if(algo.equalsIgnoreCase("DMPR") || algo.equalsIgnoreCase("MPR2hEDF")){
			System.out.println("compute2(): DMPR");
			edu.penn.rtg.csa.dmpr.Component comp_dmpr = SchedulingTreeRoot2ComponentRoot.transfer2DMPRRoot(comp, null);
			String result_dmpr = edu.penn.rtg.csa.dmpr.DMPRAnalysis.doCSAhEDF(comp_dmpr, GlobalVariable.ARVIND_SCHEDTEST_FAST);
			if(!result_dmpr.contains("SUCCESS")){
				JOptionPane.showMessageDialog(null,result_dmpr,"ERROR!",JOptionPane.ERROR_MESSAGE);
				return; 
			}
			SchedulingTreeRoot2ComponentRoot.transfer2TreeComponent(comp_dmpr, this.comp);
			comp.setResourceModel("DMPR");
		}
		if(algo.equalsIgnoreCase("CADMPR_TASKCENTRIC") || algo.equalsIgnoreCase("CAMPR2hEDF_TASKCENTRIC")){
			//TODO
			String type = "CADMPR_TASKCENTRIC";
			System.out.println("compute2(): CADMPR_TASKCENTRIC");
			edu.penn.rtg.csa.cadmpr.Component comp_cadmpr = SchedulingTreeRoot2ComponentRoot.transfer2CADMPRRoot(comp,null);
			String result_cadmpr_taskcentric = edu.penn.rtg.csa.cadmpr.CADMPRAnalysis.
					doCADMPRTaskCentricAnalysis(comp_cadmpr, GlobalVariable.TASK_CENTRIC, GlobalVariable.ARVIND_SCHEDTEST_FAST, false, 0);
			if(!result_cadmpr_taskcentric.contains("SUCCESS")){
				JOptionPane.showMessageDialog(null,result_cadmpr_taskcentric,"ERROR!",JOptionPane.ERROR_MESSAGE);
				return;
			}
			SchedulingTreeRoot2ComponentRoot.transfer2TreeComponent(comp_cadmpr, type, this.comp);
			comp.setResourceModel("CAMPR_TASKCENTRIC");
		}
		if(algo.equalsIgnoreCase("CADMPR_MODELCENTRIC") || algo.equalsIgnoreCase("CAMPR2hEDF_MODELCENTRIC")){
			String type = "CADMPR_MODELCENTRIC";
			System.out.println("compute2(): CADMPR_MODELCENTRIC");
			edu.penn.rtg.csa.cadmpr.Component comp_cadmpr = SchedulingTreeRoot2ComponentRoot.transfer2CADMPRRoot(comp,null);
			String result_cadmpr_modelcentric = edu.penn.rtg.csa.cadmpr.CADMPRAnalysis. 
					doCADMPRModelCentricAnalysis(comp_cadmpr, GlobalVariable.MODEL_CENTRIC, GlobalVariable.ARVIND_SCHEDTEST_FAST, false, 0);
			if(!result_cadmpr_modelcentric.contains("SUCCESS")){
				JOptionPane.showMessageDialog(null,result_cadmpr_modelcentric,"ERROR!",JOptionPane.ERROR_MESSAGE);
				return;
			}
			SchedulingTreeRoot2ComponentRoot.transfer2TreeComponent(comp_cadmpr, type, this.comp);
			comp.setResourceModel("CADMPR_MODELCENTRIC");
		}
		if(algo.equalsIgnoreCase("CADMPR_HYBRID") || algo.equalsIgnoreCase("CAMPR2hEDF_HYBRID")){
			String type = "CADMPR_HYBRID";
			System.out.println("compute2(): CADMPR_HYBRID");
			edu.penn.rtg.csa.cadmpr.Component comp_cadmpr = SchedulingTreeRoot2ComponentRoot.transfer2CADMPRRoot(comp,null);
			comp_cadmpr = edu.penn.rtg.csa.cadmpr.CADMPRAnalysis.
								doCADMPRHybridAnalysis(comp_cadmpr, GlobalVariable.HYBRID, GlobalVariable.ARVIND_SCHEDTEST_FAST,false, 0);
			if(comp_cadmpr.isInterfaceComputed() == false){
				JOptionPane.showMessageDialog(null,"CADMPR_HYBRID only support hEDF scheduling policy in each component","ERROR!",JOptionPane.ERROR_MESSAGE);
				return;
			}
			SchedulingTreeRoot2ComponentRoot.transfer2TreeComponent(comp_cadmpr, type, this.comp);
			comp.setResourceModel("CADMPR_HYBRID");
		}
		
		root.setProcessedRecursive(false);
		comp.setProcessedRecursive(true);
		output.displayOutput(comp, algo);
		cartsTree.updateUI();
		this.destroy();//make sure GC collect the thread immediately
	}
	
	public void destroy(){
		this.algo = null;
		this.root = null;
		this.comp = null;
		this.output = null;
		this.cartsTree = null;
		this.isCompute = false;
	}
}
